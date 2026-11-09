$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$cam = $null
$opened = $false
try {
  $request = [Console]::In.ReadToEnd() | ConvertFrom-Json
  Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using TYPEATTR=System.Runtime.InteropServices.ComTypes.TYPEATTR;
using VARDESC=System.Runtime.InteropServices.ComTypes.VARDESC;
using TYPEKIND=System.Runtime.InteropServices.ComTypes.TYPEKIND;
using VARKIND=System.Runtime.InteropServices.ComTypes.VARKIND;
public static class EffSuiteCamTypes {
  [DllImport("oleaut32.dll", PreserveSig=true)]
  static extern int LoadRegTypeLib(ref Guid id, short major, short minor, int lcid, out ITypeLib library);
  [DllImport("oleaut32.dll", CharSet=CharSet.Unicode, PreserveSig=true)]
  static extern int LoadTypeLibEx(string szFile, int regkind, out ITypeLib library);

  static void ReadLibrary(ITypeLib library, Dictionary<string,int> output, HashSet<string> wanted) {
    for(int i=0;i<library.GetTypeInfoCount();i++) {
      TYPEKIND kind; library.GetTypeInfoType(i,out kind);
      if(kind!=TYPEKIND.TKIND_ENUM && kind!=TYPEKIND.TKIND_MODULE) continue;
      ITypeInfo info;library.GetTypeInfo(i,out info);IntPtr pointer;
      info.GetTypeAttr(out pointer);
      var attr=(TYPEATTR)Marshal.PtrToStructure(pointer,typeof(TYPEATTR));
      info.ReleaseTypeAttr(pointer);
      for(int j=0;j<attr.cVars;j++) {
        info.GetVarDesc(j,out pointer);
        var desc=(VARDESC)Marshal.PtrToStructure(pointer,typeof(VARDESC));
        if(desc.varkind==VARKIND.VAR_CONST) {
          string[] names=new string[1];int count;
          info.GetNames(desc.memid,names,1,out count);
          if(count>0 && wanted.Contains(names[0]) && !output.ContainsKey(names[0])) {
            output[names[0]]=unchecked((int)Convert.ToInt64(Marshal.GetObjectForNativeVariant(desc.desc.lpvarValue)));
          }
        }
        info.ReleaseVarDesc(pointer);
      }
      Marshal.ReleaseComObject(info);
    }
    Marshal.ReleaseComObject(library);
  }

  public static Dictionary<string,int> Constants(string guid, short major, short minor, string serverPath) {
    Guid id=new Guid(guid); ITypeLib library;
    Marshal.ThrowExceptionForHR(LoadRegTypeLib(ref id,major,minor,0,out library));
    var output=new Dictionary<string,int>(StringComparer.OrdinalIgnoreCase);
    var wanted=new HashSet<string>(StringComparer.OrdinalIgnoreCase) {
      "camReadOnly","camReadWrite","camNoUpdate","camUpdate",
      "CAM_F_DENERGY","CAM_F_DEFF","CAM_F_DEFFERR","CAM_T_NCLNAME",
      "CAM_L_NCLLINE","CAM_F_NLENERGY","CAM_F_NLABUN",
      "CAM_T_CTFNUCL","CAM_F_CTFENER","CAM_F_CTFRATE","CAM_F_CTFERROR"
    };
    ReadLibrary(library, output, wanted);
    if(output.Count < wanted.Count && !string.IsNullOrEmpty(serverPath)) {
      string dir = Path.GetDirectoryName(serverPath.Trim('"'));
      if(!string.IsNullOrEmpty(dir)) {
        foreach(string dll in new string[]{"CamCtrls.dll","DataAcc.dll","DevAcc.dll","Displayr.dll"}) {
          if(output.Count >= wanted.Count) break;
          string candidate = Path.Combine(dir, dll);
          ITypeLib companion;
          if(File.Exists(candidate) && LoadTypeLibEx(candidate, 2, out companion) == 0 && companion != null) {
            ReadLibrary(companion, output, wanted);
          }
        }
      }
    }
    string[] companionGuids = new string[]{
      "{00058270-321F-11D2-B062-0060970B2CE6}",
      "{5531FC70-C3DF-11D1-9CF4-AA0004004105}",
      "{592A6920-EA90-11D2-97BD-ECB1F3000000}",
      "{07D2E9B4-09C1-11D2-85D3-204C4F4F5020}"
    };
    foreach(string cg in companionGuids) {
      if(output.Count >= wanted.Count) break;
      Guid cid = new Guid(cg); ITypeLib companion;
      if(LoadRegTypeLib(ref cid, 1, 0, 0, out companion) == 0 && companion != null) {
        ReadLibrary(companion, output, wanted);
      }
    }
    return output;
  }
}
'@
  $root = [Microsoft.Win32.Registry]::ClassesRoot
  $progid = [string]$request.progid
  if (!$progid) {
    $known = @('Canberra.CamDatasource','Canberra.CamDatasource.1','CAMSRCLib.CamDatasource','CAMSource.CamDatasource')
    foreach ($name in $known) {
      $probeKey = $root.OpenSubKey($name)
      if ($null -ne $probeKey) {
        $probeKey.Close()
        try { $cam = New-Object -ComObject $name; $progid=$name; break } catch { }
      }
    }
    if ($null -eq $cam) {
      $names = $root.GetSubKeyNames() | Where-Object { $_ -match '(?i)camdatasource' }
      $names = @($names | Sort-Object Length)
      foreach ($name in $names) {
        try { $cam = New-Object -ComObject $name; $progid=$name; break } catch { }
      }
    }
  } else { $cam = New-Object -ComObject $progid }
  if ($null -eq $cam) { throw 'Genie CamDatasource is not registered for this process architecture.' }
  $clsid = ([type]::GetTypeFromProgID($progid)).GUID.ToString('B')
  $key = $root.OpenSubKey("CLSID\$clsid\TypeLib")
  if ($null -eq $key) { throw 'Cannot find the registered CAM type library.' }
  $libid = [string]$key.GetValue('');$key.Close()
  $serverPath = ''
  $srvKey = $root.OpenSubKey("CLSID\$clsid\InprocServer32")
  if ($null -eq $srvKey) { $srvKey = $root.OpenSubKey("CLSID\$clsid\LocalServer32") }
  if ($null -ne $srvKey) { $serverPath = [string]$srvKey.GetValue(''); $srvKey.Close() }
  $key = $root.OpenSubKey("TypeLib\$libid")
  $versions = @($key.GetSubKeyNames() | Where-Object { $_ -match '^\d+\.\d+$' } | Sort-Object {[version]$_} -Descending)
  $key.Close()
  if (!$versions.Count) { throw 'The CAM type library has no registered version.' }
  $v = $versions[0].Split('.')
  $ids = [EffSuiteCamTypes]::Constants($libid,[System.Int16]$v[0],[System.Int16]$v[1],$serverPath)
  function Id([string]$name) {
    if (!$ids.ContainsKey($name)) { throw "Missing CAM constant: $name" }
    return [int]$ids[$name]
  }
  function Invoke-Cam([string]$name,[object[]]$arguments) {
    return $cam.GetType().InvokeMember($name,([Reflection.BindingFlags]::InvokeMethod -bor [Reflection.BindingFlags]::OptionalParamBinding),$null,$cam,$arguments)
  }
  function Get-Parameter([string]$name,[object[]]$indices) {
    $arguments = @((Id $name)) + $indices
    return $cam.GetType().InvokeMember('Parameter',([Reflection.BindingFlags]::GetProperty -bor [Reflection.BindingFlags]::OptionalParamBinding),$null,$cam,$arguments)
  }
  function Set-Parameter([string]$name,[object[]]$indices,$value) {
    $arguments = @((Id $name)) + $indices + @($value)
    $null = $cam.GetType().InvokeMember('Parameter',([Reflection.BindingFlags]::SetProperty -bor [Reflection.BindingFlags]::OptionalParamBinding),$null,$cam,$arguments)
  }
  $write = $request.action.StartsWith('write_')
  $mode = if ($write) { Id 'camReadWrite' } else { Id 'camReadOnly' }
  $openStatus = Invoke-Cam 'Open' @([string]$request.path,$mode)
  $opened=$true
  $rows = New-Object 'System.Collections.Generic.List[object]'
  switch ([string]$request.action) {
    'read_cal' {
      $energyParamId = Id 'CAM_F_DENERGY'
      $null = Id 'CAM_F_DEFF'
      $null = Id 'CAM_F_DEFFERR'
      for($i=1;$i -le 93;$i++) {
        try { $energy=[double](Get-Parameter 'CAM_F_DENERGY' @(1,$i)) } catch {
          if($i -eq 1) {throw "CAL first-point read failed in $([IntPtr]::Size*8)-bit CAM; Open status=$openStatus; parameter=$energyParamId. $($_.Exception.ToString())"}
          break
        }
        if($energy -le 0) {
          if($i -eq 1) {throw "CAL first energy is $energy in $([IntPtr]::Size*8)-bit CAM; Open status=$openStatus. No calibration points imported. Confirm this CAL opens in original EFFTRAN."}
          break
        }
        $eff=[double](Get-Parameter 'CAM_F_DEFF' @(1,$i))
        $unc=[double](Get-Parameter 'CAM_F_DEFFERR' @(1,$i))
        if($eff -le 0 -or $unc -lt 0) {throw 'Invalid CAM calibration value.'}
        $rows.Add(@{energy=$energy;efficiency=$eff;uncertainty=$unc})
      }
    }
    'read_nlb' {
      $null = Id 'CAM_T_NCLNAME'
      $null = Id 'CAM_L_NCLLINE'
      $null = Id 'CAM_F_NLENERGY'
      $null = Id 'CAM_F_NLABUN'
      $ended=$false
      for($r=1;$r -le 10000;$r++) {
        try { $name=[string](Get-Parameter 'CAM_T_NCLNAME' @($r)) } catch {
          if($r -eq 1) {throw "NLB first-record read failed in $([IntPtr]::Size*8)-bit CAM; Open status=$openStatus. $($_.Exception.ToString())"}
          $ended=$true;break
        }
        if(!$name.Trim()) {$ended=$true;break}
        $entryEnd=$false
        for($e=1;$e -le 10000;$e++) {
          try {$line=[int](Get-Parameter 'CAM_L_NCLLINE' @($r,$e))} catch {$entryEnd=$true;break}
          if($line -le 0) {$entryEnd=$true;break}
          $energy=[double](Get-Parameter 'CAM_F_NLENERGY' @($line))
          $abundance=[double](Get-Parameter 'CAM_F_NLABUN' @($line))
          $rows.Add(@{nuclide=$name.Trim().ToUpperInvariant();energy=$energy;abundance=$abundance;record=$r;entry=$e;line=$line})
        }
        if(!$entryEnd) {throw 'NLB line limit reached; refusing a truncated read.'}
      }
      if(!$ended) {throw 'NLB record limit reached; refusing a truncated read.'}
    }
    'read_ctf' {
      $null = Id 'CAM_T_CTFNUCL'
      $null = Id 'CAM_F_CTFENER'
      $null = Id 'CAM_F_CTFRATE'
      $ended=$false
      for($r=1;$r -le 10000;$r++) {
        try {$name=[string](Get-Parameter 'CAM_T_CTFNUCL' @($r))} catch {
          if($r -eq 1) {throw "CTF first-record read failed in $([IntPtr]::Size*8)-bit CAM; Open status=$openStatus. $($_.Exception.ToString())"}
          $ended=$true;break
        }
        if(!$name.Trim()) {$ended=$true;break}
        $energy=[double](Get-Parameter 'CAM_F_CTFENER' @($r))
        $rate=[double](Get-Parameter 'CAM_F_CTFRATE' @($r))
        $unc=0.0
        try { $unc=[double](Get-Parameter 'CAM_F_CTFERROR' @($r)) } catch {}
        $rows.Add(@{nuclide=$name.Trim().ToUpperInvariant();energy=$energy;rate=$rate;uncertainty=$unc;record=$r})
      }
      if(!$ended) {throw 'Certificate record limit reached; refusing a truncated read.'}
    }
    'write_cal' {
      foreach($u in $request.updates) {
        Set-Parameter 'CAM_F_DENERGY' @(1,[int]$u.entry) ([double]$u.energy)
        Set-Parameter 'CAM_F_DEFF' @(1,[int]$u.entry) ([double]$u.value)
        Set-Parameter 'CAM_F_DEFFERR' @(1,[int]$u.entry) ([double]$u.uncertainty)
      }
    }
    'write_nlb' {foreach($u in $request.updates) {Set-Parameter 'CAM_F_NLABUN' @([int]$u.line) ([double]$u.value)}}
    'write_ctf' {
      foreach($u in $request.updates) {
        if ($null -ne $u.energy) { Set-Parameter 'CAM_F_CTFENER' @([int]$u.record) ([double]$u.energy) }
        Set-Parameter 'CAM_F_CTFRATE' @([int]$u.record) ([double]$u.value)
        if ($null -ne $u.uncertainty) {
          try { Set-Parameter 'CAM_F_CTFERROR' @([int]$u.record) ([double]$u.uncertainty) } catch {}
        }
      }
    }
    default {throw 'Unknown CAM bridge action.'}
  }
  $closeMode=if($write){Id 'camUpdate'}else{Id 'camNoUpdate'}
  $null=Invoke-Cam 'Close' @($closeMode);$opened=$false
  if(!$write -and $rows.Count -eq 0) {throw 'CAM returned no usable records.'}
  @{ok=$true;rows=@($rows.ToArray());progid=$progid;architecture=[IntPtr]::Size*8;type_library=$libid;type_library_version=$versions[0]} | ConvertTo-Json -Depth 10 -Compress
} catch {
  @{ok=$false;error=$_.Exception.Message} | ConvertTo-Json -Compress
  exit 1
} finally {
  if($opened -and $null -ne $cam) {try {$null=Invoke-Cam 'Close' @((Id 'camNoUpdate'))}catch{}}
  if($null -ne $cam) {$null=[Runtime.InteropServices.Marshal]::FinalReleaseComObject($cam)}
}
