try:
    from MgmtWebSvcApp import g_theApp

    if __name__ == "__main__":
        g_theApp.run()
except Exception as e:
    print("Error - " + str(e))
