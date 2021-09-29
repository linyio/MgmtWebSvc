from flask import Flask
#for adding new resources (new endpoints) just import the corresponding .py file from Api sub-folder
from Api import Orgs, Entities, Info, CAs, OvpnConfigTemplatesInfo, OvpnConfigs, OvpnConfigNames, SrvsExtraInfo, \
    Certs, HostCaCert, HostCertsFingerprints
import argparse
import settings
import os

from Utils.CertsUtils import GenerateHostCACertAndKey, GenerateHostCertAndKey, CertPathFingerprint
from Utils.SettingsUtils import EnvOrSetting
import shutil
from flask_cors import CORS

class OpenvpnRestApiApp(Flask):
    def __init__(self, api, db):
        super().__init__(__name__)
        self._ConfigInit()
        self.m_api = api
        self.m_db = db
        self.m_tmpDir = None
        db.init_app(self) #register the app with the database

        # set the foreign_keys PRAGMA for activating foreign keys checks and to enable cascade delete and updates for parent tables
        # although not a singleton the app object is instantiated only once
        from sqlalchemy import event

        @event.listens_for(db.get_engine(self), "connect")
        def SetSqlitePragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        api.init_app(self)
        self._ParseArgs()
        if not self.m_args.reset_db and not self.m_args.show_certs_fingerprints and \
                not self.m_args.init_certs:
            if self.config["USER_IDS"] is None:
                raise RuntimeError(
                    "User id(s) is/are not set. They're fundametally needed, for proper JWT authorization")
            if self.config['LISTEN_MODE'] not in [ "http", "unix" ]: #don't init/generate certs for http and unix listen modes
                self.InitCerts() #might throw, in case an invalid certs configuration is found
            self.InitTmpDir()  # thoroughly init the m_tmpDir
            self._InitDb()
            CORS(self, origins = self.config["ALLOWED_ORIGINS"], expose_headers=["Content-Disposition"])

    def _ConfigInit(self):
        self.config['HOST'] = EnvOrSetting("HOST", "FLASK_HOST", "localhost")
        self.config['PORT'] = EnvOrSetting("PORT", "FLASK_PORT", "8083")
        self.config['SERVER_NAME'] = EnvOrSetting("SERVER_NAME", "FLASK_SERVER_NAME",
                                                  f'{self.config["HOST"]}:{self.config["PORT"]}') #automatically read by run method
        self.config['LISTEN_MODE'] = os.getenv("LISTEN_MODE", "https").lower()
        if self.config['LISTEN_MODE'] not in [ 'https', "http", "unix"]:#unix mode valid only in uWSGI envs
            self.config['LISTEN_MODE'] = "https"
        self.config['CERTS_DIR'] =  os.path.realpath(EnvOrSetting("CERTS_DIR", "FLASK_CERTS_DIR",
                                                  os.path.join(os.path.dirname(os.path.realpath(__file__)), "..",
                                                               "Certs"))) #relative to the current script path
        self.config['ALLOWED_ORIGINS'] = EnvOrSetting("ALLOWED_ORIGINS", "FLASK_ALLOWED_ORIGINS", ["https://www.liny.io"])
        self.config["USER_IDS"] = EnvOrSetting("USER_IDS", "FLASK_USER_IDS")
        if type(self.config["USER_IDS"]) is str:
            self.config["USER_IDS"] = [userId.strip() for userId in self.config["USER_IDS"].split(",")]
        self.config['SQLALCHEMY_DATABASE_URI'] = EnvOrSetting("DB_URL", "SQLALCHEMY_DATABASE_URI",
                                                              'sqlite:///../db.sqlite') + \
            ( "?check_same_thread=False"
                if not EnvOrSetting("SQLALCHEMY_CHECK_SAME_THREAD", "SQLALCHEMY_CHECK_SAME_THREAD", True)
                else "" )
        self.config['SQLALCHEMY_ECHO'] = EnvOrSetting("SQLALCHEMY_ECHO")
        self.config['SQLALCHEMY_RECORD_QUERIES'] = EnvOrSetting("SQLALCHEMY_RECORD_QUERIES")
        self.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = EnvOrSetting("SQLALCHEMY_TRACK_MODIFICATIONS")
        self.config['JSON_SORT_KEYS'] = False
        self.config['SWAGGER_UI_DOC_EXPANSION'] = EnvOrSetting("REST_SWAGGER_UI_DOC_EXPANSION")
        self.config['RESTPLUS_VALIDATE'] = EnvOrSetting("REST_VALIDATE")
        self.config['RESTPLUS_MASK_SWAGGER'] = EnvOrSetting("REST_MASK_SWAGGER")
        self.config['ERROR_404_HELP'] = EnvOrSetting("REST_ERROR_404_HELP")

    def _ParseArgs(self):
        self.m_argParser = argparse.ArgumentParser(description="Management rest api")
        self.m_argParser.add_argument("--reset-db", action="store_true", help="resets the sqlite database and exits")
        self.m_argParser.add_argument("--init-certs", action="store_true",
                                      help="just generate the host's CA and ssl cert and key, if necessary, needed for "
                                           "exposing the service over https")
        self.m_argParser.add_argument("--show-certs-fingerprints", action="store_true", help="shows the host cert and CA "
                                                                                          "certs' fingerprints")
        self.m_args = self.m_argParser.parse_args()

    def run(self, **kwargs):
        if self.m_args.init_certs:
            self.InitCerts()
        if self.m_args.reset_db:
            self._ResetDb()
        if self.m_args.show_certs_fingerprints:
            self.ShowCertsFingerprints()
        if not self.m_args.reset_db and not self.m_args.show_certs_fingerprints and not self.m_args.init_certs:
            #it's super important to just call the parent's run method here, since this method isn't called  by uWSGI
            super().run(debug=EnvOrSetting("FLASK_DEBUG", defaultValue=False),
                        use_reloader=EnvOrSetting("FLASK_RELOADER", defaultValue=False),
                        ssl_context=(self.CertPath(), self.KeyPath())
                        if self.config['LISTEN_MODE'] == "https" else None)
        print("Done!")

    from flask_sqlalchemy import SQLAlchemy
    def Db(self) -> SQLAlchemy:
        return self.m_db

    def _ResetDb(self):
        print("Resetting database ...")
        with self.app_context():
            self.m_db.drop_all()
        self._InitDb()

    def _InitDb(self):
        with self.app_context():
            self.m_db.create_all()

            #add entities types records
            from Database.Models import EntityTypeEnum, EntityTypeDbModel
            if EntityTypeDbModel.query.count() == 0:
                for entityType in EntityTypeEnum:
                    entityTypeDbRec = EntityTypeDbModel()
                    entityTypeDbRec.id = entityType.value
                    entityTypeDbRec.name = entityType.name
                    self.m_db.session.add(entityTypeDbRec)
                self.m_db.session.commit()

    def InitTmpDir(self):
        if EnvOrSetting("FLASK_CLEAN_TMP_BASE_AT_STARTUP", defaultValue=False):
            self.CleanTmpBaseDir() #cleanup tmp basedir in case the previous process ended abruptly
        os.makedirs(EnvOrSetting("FLASK_TMP_BASE"), 0o755, True)

        from tempfile import TemporaryDirectory

        class SafeCleanulTmpDir(TemporaryDirectory):
            @classmethod
            def _cleanup(cls, name, warn_message):
                try:
                    super()._cleanup(name, warn_message)
                except:
                    pass

        self.m_tmpDir = SafeCleanulTmpDir(None, "MgmtWebSvc-", EnvOrSetting("FLASK_TMP_BASE"))

    def CleanTmpBaseDir(self): #preserve the temporary dir
        self.CleanDir(EnvOrSetting("FLASK_TMP_BASE"))

    def CleanTmpDir(self): #remove also the tmp dir. Should be called only at the server tear-down operation
        self.m_tmpDir.cleanup()

    @staticmethod
    def CleanDir(directory):
        for root, dirs, files in os.walk(directory):
            for fileItem in files:
                os.remove(os.path.join(root, fileItem))
            for dirItem in dirs:
                try:
                    shutil.rmtree(os.path.join(root, dirItem), ignore_errors=True)
                except:
                    pass
            break

    def CaCertDir(self):
        return os.path.join(self.config["CERTS_DIR"], "CA")

    def CaCertPath(self):
        return os.path.join(self.CaCertDir(), "ca.crt")

    def CertPath(self):
        return self.CertPathBase() + ".crt"

    def KeyPath(self):
        return self.CertPathBase() + ".key"

    def CertPathBase(self):
        return os.path.join(self.config['CERTS_DIR'], f'{self.config["HOST"]}-{self.config["PORT"]}')

    def InitCerts(self):
        def CheckKeyCertPair(checkCertsDir, checkCertsName):
            foundFiles = 0
            for ext in [".crt", ".key"]:
                if os.path.exists(os.path.join(checkCertsDir, checkCertsName + ext)):
                    foundFiles += 1
            return foundFiles

        certsDir = self.config['CERTS_DIR']
        caCertDir = self.CaCertDir()
        # for path in [certsDir, caCertDir]:
        #     os.makedirs(path, exist_ok=True)
        os.makedirs(caCertDir, exist_ok=True)

        #Todo: check if certs are also expired
        caFilesNo = CheckKeyCertPair(caCertDir, "ca")
        if caFilesNo == 0:
            import platform
            GenerateHostCACertAndKey(self, caCertDir, EnvOrSetting("CA_CN", defaultValue=f'{self.config["HOST"]} CA'))
        elif caFilesNo == 1:
            raise RuntimeError(f"Only the CA ssl certificate or key found. Check \"{caCertDir}\" directory",
                               caCertDir)

        hostCertKeyFilesNo = CheckKeyCertPair(certsDir, f'{self.config["HOST"]}-{self.config["PORT"]}')
        if hostCertKeyFilesNo == 0:
            GenerateHostCertAndKey(self, certsDir, os.path.join(caCertDir, "ca.crt"),
                                   os.path.join(caCertDir, "ca.key"))
        elif hostCertKeyFilesNo == 1:
            raise RuntimeError(f"Only the host's ssl certificate or key found. Check \"{certsDir}\" directory",
                               certsDir)

    def ShowCertsFingerprints(self):
        print("Fingerprints algorithm: SHA1")
        print("Fingerprints:")
        print("\tHost CA cert: " + CertPathFingerprint(self.CaCertPath()))
        print("\tHost cert: " + CertPathFingerprint(self.CertPath()))
