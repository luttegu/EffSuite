import multiprocessing
if __name__=="__main__":
    multiprocessing.freeze_support()
    from effsuite.app_cli import main
    raise SystemExit(main())
