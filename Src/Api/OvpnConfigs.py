from flask_restx import abort
from Api import g_theApi
from Utils import CertsUtils

# @g_theApi.route("/ovpnConfigs/userId/<int:userId>/srvId/<int:srvId>/os/<string:os>/srvHost/<string:srvHost>",
from Utils.ResourcesUtils import JWTAuthResource


@g_theApi.route("/ovpnConfigs/orgId/<int:orgId>/entityId/<int:entityId>", defaults = {
    "srvId": None
})
@g_theApi.route("/ovpnConfigs/orgId/<int:orgId>/entityId/<int:entityId>/srvId/<int:srvId>",
                # defaults = {"template": "InternetAccess"},
                doc={"params": {"entityId": "the entity (user/server) id for which the config is generated"}})
class OvpnConfigs(JWTAuthResource):
    """
        The Ovpn client config rest resource
    """

    def get(self, orgId, entityId, srvId):
        """
            Generates the Ovpn client/server config.  If entity id is a user he's meant to connect to server id

            It creates all the needed info if missing, such as CAs, certs and private keys.
            The server info has to already exist. Otherwise a 412 http status code will be returned

        :return: the client configuration file/archive
        """
        from flask import request as req
        from Utils.ResourcesUtils import GetEntity
        from Api.OvpnConfigTemplates import GetConfigTemplatesClass
        from Api.OvpnConfigTemplates.Utils import EntityTypeToConfigTemplateType, ClientConfigVarsFromReqArgs, \
            SrvConfigVarsFromReqArgs

        # if srvId is None:
        #     srvId = entityId
        entity, entityType = GetEntity(entityId)
        if entityType == "user":
            if srvId is None:
                abort(400, "Missing srvId")
            srv, srvType = GetEntity(srvId)
            if srvType != "server":
                abort(400, f"Entity {srvId} is not a server")
            EntityConfigVarsFromReqArgs = ClientConfigVarsFromReqArgs
        else:
            srvId = entityId
            EntityConfigVarsFromReqArgs = SrvConfigVarsFromReqArgs
        configTemplateClass = GetConfigTemplatesClass(req.args.get("configTemplateId", None, int),
                                                          EntityTypeToConfigTemplateType(entityType))
        if configTemplateClass is not None:
            app = g_theApi.app
            from Api.OvpnConfigTemplates.Utils import ConfigFromReqArgs, DateTimeFromStr
            config = ConfigFromReqArgs(req.args, [
                {
                    "name":  "caValidFrom",
                    "reqSearchNames": ["caValidFrom", "validFrom"], #fallback to validFrom
                    "post": DateTimeFromStr
                }, {
                    "name":  "validFrom",
                    "reqSearchNames": ["validFrom"],
                    "post": DateTimeFromStr
                }, {
                    "name":  "caValidity",
                    "reqSearchNames": ["caValidity", "validity"], #fallback to validity
                    "type": int
                }, {
                    "name": "validity",
                    "reqSearchNames": ["validity"],
                    "type": int
                }
            ])
            caCert, caKey = CertsUtils.GetCaCertAndKey(app, orgId, config)
            config = ConfigFromReqArgs(req.args, [
                {
                    "name": "validFrom",
                    "post": DateTimeFromStr
                },
                {
                    "name": "validity",
                    "type": int
                }
            ], config)
            cert, key = CertsUtils.GetCertAndKey(app, entityId, orgId, {
                **config,
                "srvType": entityType == "server"
            })
            configStream, configName = configTemplateClass({
                **EntityConfigVarsFromReqArgs(req.args),
                "entityName": entity.name,
                "caCert": caCert,
                "caKey": caKey,
                "cert": cert,
                "key": key,
                "tlsKey": CertsUtils.GetSrvExtraInfo(app, srvId),
                "tmpDir": app.m_tmpDir.name,
                "crl": CertsUtils.GetCRL(app, orgId, {
                    "serialize": True,
                    **config,
                })
            }).Instantiate()
            # send config to the client
            import flask
            import io
            if isinstance(configStream, (io.BytesIO, io.StringIO)) and "wsgi.file_wrapper" in flask.request.environ:
                del (flask.request.environ["wsgi.file_wrapper"])  # delete the wsgi filewapper since memory stream objs can't be offloaded
            return flask.send_file(configStream, as_attachment=True, attachment_filename=configName,
                                   cache_timeout=-1)
        else:
            abort(400, "Invalid config template id")
