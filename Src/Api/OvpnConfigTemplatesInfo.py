from flask_restx import abort
from Api import g_theApi
from Utils.ResourcesUtils import JWTAuthResource


@g_theApi.route("/ovpnConfigTemplatesInfo",
                doc={"description": "retrieve the configuration template list"})
class OvpnConfigTemplatesInfo(JWTAuthResource):
    def get(self):
        from flask import request as req
        from Api.OvpnConfigTemplates import g_ovpnConfigTemplates

        try:
            return [{
                **{key: configTemplate[key] for key in ("id", "version", "type", "name", "description", "default")},
            } for configTemplate in (
                filter(lambda configTemplate: req.args["type"] == configTemplate["type"], g_ovpnConfigTemplates)
                if "type" in req.args else g_ovpnConfigTemplates)], 200
        except KeyError as e:
            abort(500, f"Unknown config template info field - {e}")
        except Exception as e:
            abort(500, f"Error retrieving config template info - {e}")
