from flask_restx import fields as FlaskRestPlusFields
from Api import g_theApi
from Database.Models import CasDbModel, CertsDbModel
from marshmallow import Schema, fields, post_load, validate as mmValidate
from Utils.ModelUtils import ModelFromSchema
from Utils import ResourcesUtils

#CA marshmallow schema
from Utils.ResourcesUtils import JWTAuthResource


class CaSchema(Schema):
    orgId = fields.Integer(required=True, description="CA's associated org id")

from flask_restx.model import Model
g_casModelOut: Model = g_theApi.model("Output CA model",
                                      {"id": FlaskRestPlusFields.Integer(description="CA's id"),
     **ModelFromSchema(CaSchema)
    })

g_casModel: Model = g_theApi.model("CAs model",
                {
                    "pagination" : FlaskRestPlusFields.Boolean(required=True, description="States if pagination is enabled or not"),
                    "total_items" : FlaskRestPlusFields.Integer(description="Total number of items in the collection. Missing if pagination is False"),
                    "page" : FlaskRestPlusFields.Integer(description="The page number. Missing if pagination is False"),
                    "perPage" : FlaskRestPlusFields.Integer(description="Per page items no. Missing if pagination is False"),
                    "cas" : FlaskRestPlusFields.List(FlaskRestPlusFields.Nested(g_casModelOut),
                                                     description="CAs list")
                })

@g_theApi.route("/cas")
class CasPaginated(JWTAuthResource):
    """
        The CAs rest resource
    """

    @g_theApi.marshal_with(g_casModel, skip_none=True)
    def get(self):
        """
            Gets the CAs list

        :return: a paged/unpaged list of CAs
        """
        return ResourcesUtils.Get(CasDbModel, {
            "page": ResourcesUtils.ReqSafeArg("page", 0),
            "perPage": ResourcesUtils.ReqSafeArg("perPage", 10)
        })

@g_theApi.route("/cas/caId/<int:caId>", doc={"params": {"caId": "the CA's id"}})
class CasId(JWTAuthResource):
    def delete(self, caId):
        dbSession = g_theApi.app.Db().session
        try:
            caQuery = CasDbModel.query.filter(CasDbModel.id == caId)
            caDbObj = caQuery.first()
            caQuery.delete(synchronize_session=False)
            # dbSession.delete(caDbObj, synchronize_session=False)
            CertsDbModel.query.filter(CertsDbModel.orgId == caDbObj.orgId).delete(synchronize_session=False)
            # dbSession.delete(CertsDbModel.query.filter(CertsDbModel.orgId == caDbObj.orgId), synchronize_session=False)
            dbSession.commit()
        except Exception as e:
            return {"message": "Error deleting CA along its certificates - " + str(e)}, 500