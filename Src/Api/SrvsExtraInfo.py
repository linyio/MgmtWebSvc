from marshmallow import Schema, fields, post_load
from Api import g_theApi
from Database.Models import ServersExtraInfoDbModel
from flask_restx.model import Model
from Utils.ModelUtils import ModelFromSchema
from Utils import ResourcesUtils
from Utils.ResourcesUtils import JWTAuthResource


class SrvExtraInfoSchema(Schema):
    _entityName = "srvExtraInfo"

    srvId = fields.Integer(required=True, description="The server entity id the extra info is associated with")
    # tlsKey = fields.String(required=False, description="The tls auth simetric key", default="")

    @post_load
    def CreateSrvExtraInfo(self, data, **kwargs):
        if "tlsKey" not in data:
            data["tlsKey"] = b""
        return ServersExtraInfoDbModel(**data)


g_srvExtraInfoModel: Model = g_theApi.model("Input server extra info model",
                                            ModelFromSchema(SrvExtraInfoSchema))


@g_theApi.route("/srvExtraInfo")
class SrvsExtraInfo(JWTAuthResource):
    def get(self):
        """
            Get the exra info associations
        :return:
        """
        return {
            "srvsExtraInfo": [{
                "srvId": srvExtraInfo[0],
            } for srvExtraInfo in ResourcesUtils.Get(ServersExtraInfoDbModel, {
                "pagge": -1,
                "columns": [ServersExtraInfoDbModel.srvId],
                "collectionName": "srvsExtraInfo"
            })["srvsExtraInfo"]]}
