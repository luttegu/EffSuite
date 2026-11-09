import multiprocessing
if __name__=="__main__":
    multiprocessing.freeze_support()
    import faulthandler
    from pathlib import Path
    import traceback
    path=Path.home()/"Documents/EffSuite/Logs";path.mkdir(parents=True,exist_ok=True)
    with (path/"gui_startup.log").open("a",encoding="utf-8",buffering=1) as log:
        faulthandler.enable(log)
        try:
            from effsuite.gui import main
            result=main()
        except Exception as exc:
            traceback.print_exc(file=log)
            import sys
            if sys.platform=="win32":
                import ctypes
                ctypes.windll.user32.MessageBoxW(None,str(exc)+"\n\nDetails: "+str(path/"gui_startup.log"),"EffSuite could not start",16)
            raise
    raise SystemExit(result)
