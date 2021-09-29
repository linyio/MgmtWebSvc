import flask
from flask_restx import Resource
from Api import g_theApi
from Utils.CertsUtils import CertPathFingerprint

@g_theApi.route("/hostcertsfingerprints")
class HostCaCert(Resource):
    def get(self):
        app = g_theApi.app
        return {
            "fingerprintsAlgorithm": "SHA1",
            "fingerprints": {
                "hostCaCert": CertPathFingerprint(app.CaCertPath()),
                "hostCert": CertPathFingerprint(app.CertPath()),
            }
        }
