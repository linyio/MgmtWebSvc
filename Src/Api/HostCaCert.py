import flask
from flask_restx import Resource
from Api import g_theApi

@g_theApi.route("/hostcacert")
class HostCaCert(Resource):
    def get(self):
        app = g_theApi.app
        return flask.send_file(app.CaCertPath(), attachment_filename=f"{app.config['HOST']}-ca.crt",
                               mimetype="application/x-x509-ca-cert",
                               as_attachment=True
                              )
