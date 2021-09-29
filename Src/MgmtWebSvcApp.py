from App import OpenvpnRestApiApp
from Api import g_theApi
from Database import db

g_theApp = OpenvpnRestApiApp(g_theApi, db)
