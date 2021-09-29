# from flask_restx import Resource, fields as FlaskRestPlusFields
from Api import g_theApi
# from marshmallow import Schema, fields, post_load, validate as mmValidate
from marshmallow import Schema, fields
from Utils.ModelUtils import ModelFromSchema
# from Utils import ResourcesUtils
from Database.Models import OrgDbModel, EntityDbModel, EntityTypeEnum

#Orgs marshmallow schema
from Utils.ResourcesUtils import JWTAuthResource
from Utils.SettingsUtils import EnvOrSetting


class InfoSchema(Schema):
    minorVersion = fields.Integer(required=True, description='Minor version - increments on backward compatible changes,'
                                                             ' such as new features')
    revision = fields.Integer(required=True, description='Revision - increments on bugs fixes')
    stats = fields.List(fields.String(required=True, description='Enabled APIs'))

from flask_restx.model import Model
#build flask_restx model out of marshmallow schema, for using it with @api.marshal_with decorator
g_infoModel: Model = g_theApi.model("Info model",
                      ModelFromSchema(InfoSchema))


@g_theApi.route("/info")
class Info(JWTAuthResource):
    """
        The Info rest resource
    """
    @g_theApi.marshal_with(g_infoModel, skip_none=True)
    def get(self):
        """
            Gets info

        :return: the info
        """
        entitiesInfo = {
            # "total": EntityDbModel.query.count()
            "total": 0
        }
        entitiesLimitNo = EnvOrSetting("LIMIT_ENTITIES", None, 100000)
        totalEntitiesCount = 0
        for entityType in EntityTypeEnum:
            currentTypeEntitiesCount = EntityDbModel.query.\
                filter(EntityDbModel.typeId == entityType.value).limit(entitiesLimitNo).count()
            totalEntitiesCount += currentTypeEntitiesCount
            entitiesInfo[entityType.name + "s"] = currentTypeEntitiesCount
            entitiesLimitNo-= currentTypeEntitiesCount
        entitiesInfo["total"] = totalEntitiesCount
        return {
            "minorVersion": 0,
            "revision": 0,
            "stats": {
                "orgs": OrgDbModel.query.limit(EnvOrSetting("LIMIT_ORGS", None, 1000)).count(),
                "entities": entitiesInfo
            }
        }
