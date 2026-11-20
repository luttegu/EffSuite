# genie_cam.ps1 - reads and writes Genie 2000 CAM files (.CAL, .NLB, .CTF).
#
# Genie stores calibrations (.CAL), nuclide libraries (.NLB) and certificates
# (.CTF) in its own binary "CAM" format. Only Genie's own COM component
# (CamDatasource) can read and write that format safely, so this script uses it.
#
# How it is called (see genie.py):
#   Python starts Windows PowerShell with a tiny starter command. The starter
#   reads this whole script and the request from standard input and runs the
#   script with the request as its only parameter.
#
# The request has these fields:
#   action  : "read_cal", "read_nlb", "read_ctf",
#             "write_cal", "write_nlb" or "write_ctf"
#   path    : the file to open
#   updates : (write only) the new values to store
#   progid  : optional COM name of CamDatasource ("" = find it automatically)
#
# The answer is ONE line of JSON printed on standard output:
#   { "ok": true,  "rows": [...], "progid": ..., ... }   on success
#   { "ok": false, "error": "..." }                      on failure
#
# A "write_..." action writes the new values, saves the file, then REOPENS it
# read-only and returns the rows it reads back. Python compares them with what
# it asked for, so a value that was not really saved is always detected.
# Doing write + read-back in one PowerShell start saves about 2 seconds.
param($request)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

$cam = $null   # the CamDatasource COM object
# Shared state. A hashtable is used so that functions can change it.
#   fileIsOpen : true while a CAM file is open (so we can close it after an error)
#   openStatus : value returned by Open, shown in some error messages
$state = @{ fileIsOpen = $false; openStatus = $null }

# ---------------------------------------------------------------------------
# Helper written in C#: reads the numeric value of CAM constants such as
# "CAM_F_NLABUN" from Genie's registered type libraries. PowerShell cannot do
# this by itself. (Compiling this block takes about 0.4 s per start.)
# ---------------------------------------------------------------------------
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

  // Copies every wanted constant found in one type library into "output".
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

  // Looks in the main CAM type library first, then in the companion Genie
  // libraries, until every wanted constant has been found.
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

# ---------------------------------------------------------------------------
# Small helpers around the COM object
# ---------------------------------------------------------------------------

# Creates the CamDatasource COM object. Returns the object and its COM name.
function New-CamObject([string]$requestedProgId) {
  if ($requestedProgId) {
    return @{ object = (New-Object -ComObject $requestedProgId); progid = $requestedProgId }
  }
  $root = [Microsoft.Win32.Registry]::ClassesRoot
  # 1) The usual names used by Genie 2000.
  foreach ($name in @('Canberra.CamDatasource', 'Canberra.CamDatasource.1', 'CAMSRCLib.CamDatasource', 'CAMSource.CamDatasource')) {
    $key = $root.OpenSubKey($name)
    if ($null -eq $key) { continue }
    $key.Close()
    try { return @{ object = (New-Object -ComObject $name); progid = $name } } catch { }
  }
  # 2) Any other registered name containing "camdatasource" (slow: scans the registry).
  $names = @($root.GetSubKeyNames() | Where-Object { $_ -match '(?i)camdatasource' } | Sort-Object Length)
  foreach ($name in $names) {
    try { return @{ object = (New-Object -ComObject $name); progid = $name } } catch { }
  }
  throw 'Genie CamDatasource is not registered for this process architecture.'
}

# Finds the type library of the COM object and reads the CAM constants from it.
function Get-CamConstants([string]$progid) {
  $root = [Microsoft.Win32.Registry]::ClassesRoot
  $clsid = ([type]::GetTypeFromProgID($progid)).GUID.ToString('B')

  $key = $root.OpenSubKey("CLSID\$clsid\TypeLib")
  if ($null -eq $key) { throw 'Cannot find the registered CAM type library.' }
  $libraryId = [string]$key.GetValue('')
  $key.Close()

  $serverPath = ''
  $key = $root.OpenSubKey("CLSID\$clsid\InprocServer32")
  if ($null -eq $key) { $key = $root.OpenSubKey("CLSID\$clsid\LocalServer32") }
  if ($null -ne $key) { $serverPath = [string]$key.GetValue(''); $key.Close() }

  # Use the highest registered version of the type library.
  $key = $root.OpenSubKey("TypeLib\$libraryId")
  $versions = @($key.GetSubKeyNames() | Where-Object { $_ -match '^\d+\.\d+$' } | Sort-Object { [version]$_ } -Descending)
  $key.Close()
  if (!$versions.Count) { throw 'The CAM type library has no registered version.' }
  $major, $minor = $versions[0].Split('.')

  $values = [EffSuiteCamTypes]::Constants($libraryId, [Int16]$major, [Int16]$minor, $serverPath)
  return @{ values = $values; library = $libraryId; version = $versions[0] }
}

# Returns the number of a CAM constant, e.g. Id 'CAM_F_NLABUN'.
function Id([string]$name) {
  if (!$constants.ContainsKey($name)) { throw "Missing CAM constant: $name" }
  return [int]$constants[$name]
}

# Calls a method of the COM object (late binding, works in 32 and 64 bit).
function Invoke-Cam([string]$method, [object[]]$arguments) {
  $flags = [Reflection.BindingFlags]::InvokeMethod -bor [Reflection.BindingFlags]::OptionalParamBinding
  return $cam.GetType().InvokeMember($method, $flags, $null, $cam, $arguments)
}

# Reads one CAM parameter, e.g. Get-Parameter 'CAM_F_NLABUN' @(lineNumber).
function Get-Parameter([string]$name, [object[]]$indices) {
  $flags = [Reflection.BindingFlags]::GetProperty -bor [Reflection.BindingFlags]::OptionalParamBinding
  return $cam.GetType().InvokeMember('Parameter', $flags, $null, $cam, (@((Id $name)) + $indices))
}

# Writes one CAM parameter.
function Set-Parameter([string]$name, [object[]]$indices, $value) {
  $flags = [Reflection.BindingFlags]::SetProperty -bor [Reflection.BindingFlags]::OptionalParamBinding
  $null = $cam.GetType().InvokeMember('Parameter', $flags, $null, $cam, (@((Id $name)) + $indices + @($value)))
}

function Open-CamFile([string]$path, [bool]$forWriting) {
  $mode = if ($forWriting) { Id 'camReadWrite' } else { Id 'camReadOnly' }
  $state.openStatus = Invoke-Cam 'Open' @($path, $mode)
  $state.fileIsOpen = $true
}

function Close-CamFile([bool]$saveChanges) {
  $mode = if ($saveChanges) { Id 'camUpdate' } else { Id 'camNoUpdate' }
  $null = Invoke-Cam 'Close' @($mode)
  $state.fileIsOpen = $false
}

$bits = [IntPtr]::Size * 8   # 32 or 64: shown in error messages

# ---------------------------------------------------------------------------
# Reading. Each function returns a list of rows (one hashtable per line).
# The CAM files have no "number of lines" field, so we read until the first
# empty entry (or until reading fails).
# ---------------------------------------------------------------------------

# .CAL: up to 93 efficiency points (energy, efficiency, absolute uncertainty).
function Read-Calibration {
  $rows = New-Object 'System.Collections.Generic.List[object]'
  foreach ($name in 'CAM_F_DENERGY', 'CAM_F_DEFF', 'CAM_F_DEFFERR') { $null = Id $name }
  for ($point = 1; $point -le 93; $point++) {
    try { $energy = [double](Get-Parameter 'CAM_F_DENERGY' @(1, $point)) }
    catch {
      if ($point -eq 1) { throw "CAL first-point read failed in $bits-bit CAM; Open status=$($state.openStatus). $($_.Exception.ToString())" }
      break
    }
    if ($energy -le 0) {
      if ($point -eq 1) { throw "CAL first energy is $energy in $bits-bit CAM; Open status=$($state.openStatus). No calibration points imported. Confirm this CAL opens in original EFFTRAN." }
      break
    }
    $efficiency = [double](Get-Parameter 'CAM_F_DEFF' @(1, $point))
    $uncertainty = [double](Get-Parameter 'CAM_F_DEFFERR' @(1, $point))
    if ($efficiency -le 0 -or $uncertainty -lt 0) { throw 'Invalid CAM calibration value.' }
    $rows.Add(@{ energy = $energy; efficiency = $efficiency; uncertainty = $uncertainty })
  }
  Write-Output -NoEnumerate $rows   # return the list itself, not its items one by one
}

# .NLB: nuclide records; each record points to its gamma lines.
function Read-NuclideLibrary {
  $rows = New-Object 'System.Collections.Generic.List[object]'
  foreach ($name in 'CAM_T_NCLNAME', 'CAM_L_NCLLINE', 'CAM_F_NLENERGY', 'CAM_F_NLABUN') { $null = Id $name }
  $reachedEnd = $false
  for ($record = 1; $record -le 10000; $record++) {
    try { $nuclide = [string](Get-Parameter 'CAM_T_NCLNAME' @($record)) }
    catch {
      if ($record -eq 1) { throw "NLB first-record read failed in $bits-bit CAM; Open status=$($state.openStatus). $($_.Exception.ToString())" }
      $reachedEnd = $true; break
    }
    if (!$nuclide.Trim()) { $reachedEnd = $true; break }

    $linesEnded = $false
    for ($entry = 1; $entry -le 10000; $entry++) {
      try { $line = [int](Get-Parameter 'CAM_L_NCLLINE' @($record, $entry)) } catch { $linesEnded = $true; break }
      if ($line -le 0) { $linesEnded = $true; break }
      $energy = [double](Get-Parameter 'CAM_F_NLENERGY' @($line))
      $abundance = [double](Get-Parameter 'CAM_F_NLABUN' @($line))
      $rows.Add(@{ nuclide = $nuclide.Trim().ToUpperInvariant(); energy = $energy; abundance = $abundance
                   record = $record; entry = $entry; line = $line })
    }
    if (!$linesEnded) { throw 'NLB line limit reached; refusing a truncated read.' }
  }
  if (!$reachedEnd) { throw 'NLB record limit reached; refusing a truncated read.' }
  Write-Output -NoEnumerate $rows
}

# .CTF: one record per certified line (nuclide, energy, emission rate).
function Read-Certificate {
  $rows = New-Object 'System.Collections.Generic.List[object]'
  foreach ($name in 'CAM_T_CTFNUCL', 'CAM_F_CTFENER', 'CAM_F_CTFRATE') { $null = Id $name }
  $reachedEnd = $false
  for ($record = 1; $record -le 10000; $record++) {
    try { $nuclide = [string](Get-Parameter 'CAM_T_CTFNUCL' @($record)) }
    catch {
      if ($record -eq 1) { throw "CTF first-record read failed in $bits-bit CAM; Open status=$($state.openStatus). $($_.Exception.ToString())" }
      $reachedEnd = $true; break
    }
    if (!$nuclide.Trim()) { $reachedEnd = $true; break }
    $energy = [double](Get-Parameter 'CAM_F_CTFENER' @($record))
    $rate = [double](Get-Parameter 'CAM_F_CTFRATE' @($record))
    $uncertainty = 0.0
    try { $uncertainty = [double](Get-Parameter 'CAM_F_CTFERROR' @($record)) } catch { }  # optional field
    $rows.Add(@{ nuclide = $nuclide.Trim().ToUpperInvariant(); energy = $energy; rate = $rate
                 uncertainty = $uncertainty; record = $record })
  }
  if (!$reachedEnd) { throw 'Certificate record limit reached; refusing a truncated read.' }
  Write-Output -NoEnumerate $rows
}

# ---------------------------------------------------------------------------
# Writing. Each update says where to write ("entry", "line" or "record") and
# the new value(s).
# ---------------------------------------------------------------------------
function Write-Updates([string]$kind, $updates) {
  foreach ($update in $updates) {
    switch ($kind) {
      'cal' {
        Set-Parameter 'CAM_F_DENERGY' @(1, [int]$update.entry) ([double]$update.energy)
        Set-Parameter 'CAM_F_DEFF'    @(1, [int]$update.entry) ([double]$update.value)
        Set-Parameter 'CAM_F_DEFFERR' @(1, [int]$update.entry) ([double]$update.uncertainty)
      }
      'nlb' { Set-Parameter 'CAM_F_NLABUN'  @([int]$update.line)   ([double]$update.value) }
      'ctf' { Set-Parameter 'CAM_F_CTFRATE' @([int]$update.record) ([double]$update.value) }
    }
  }
}

# ---------------------------------------------------------------------------
# Main program
# ---------------------------------------------------------------------------
try {
  $action, $kind = ([string]$request.action).Split('_')
  if ($action -notin 'read', 'write' -or $kind -notin 'cal', 'nlb', 'ctf') { throw 'Unknown CAM bridge action.' }

  $created = New-CamObject ([string]$request.progid)
  $cam = $created.object
  $typeInfo = Get-CamConstants $created.progid
  $constants = $typeInfo.values

  if ($action -eq 'write') {
    Open-CamFile ([string]$request.path) $true
    Write-Updates $kind $request.updates
    Close-CamFile $true    # save the changes
  }

  # Read the file (for a write: read it back, to prove the values were saved).
  Open-CamFile ([string]$request.path) $false
  switch ($kind) {
    'cal' { $rows = Read-Calibration }
    'nlb' { $rows = Read-NuclideLibrary }
    'ctf' { $rows = Read-Certificate }
  }
  Close-CamFile $false
  if ($rows.Count -eq 0) { throw 'CAM returned no usable records.' }

  @{ ok = $true; rows = @($rows.ToArray()); progid = $created.progid; architecture = $bits
     type_library = $typeInfo.library; type_library_version = $typeInfo.version } | ConvertTo-Json -Depth 10 -Compress
}
catch {
  @{ ok = $false; error = $_.Exception.Message } | ConvertTo-Json -Compress
}
finally {
  # Always close the file and release the COM object, even after an error.
  if ($state.fileIsOpen -and $null -ne $cam) { try { Close-CamFile $false } catch { } }
  if ($null -ne $cam) { $null = [Runtime.InteropServices.Marshal]::FinalReleaseComObject($cam) }
}
