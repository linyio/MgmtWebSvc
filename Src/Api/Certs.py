from flask_restx import fields as FlaskRestPlusFields, abort
from Api import g_theApi
from Database.Models import CertsDbModel
from marshmallow import Schema, fields, post_load, validate as mmValidate
from Utils.ModelUtils import ModelFromSchema
from Utils import ResourcesUtils, CertsUtils
from Utils.ResourcesUtils import JWTAuthResource

#Cert marshmallow schema
class CertSchema(Schema):
    entityId = fields.Integer(required=True, description="certificate's entity (server or user) id")
    orgId = fields.Integer(required=True, description="certificate's associated org id")
    srvType = fields.Boolean(required=True, description="if true then the certificate describes a server rather than an user")
    revoked = fields.Boolean(required=True, description="if true then the certificate is revoked")

    # @post_load
    # def CreateCert(self, data, **kwargs):
    #     return CertDbModel(**data)

class CertPatchSchema(Schema):
    attr = fields.String(required=True, description="The attribute to be modified",
                         validate=mmValidate.OneOf(["revoked"]))
    operation = fields.String(required=False, description="The operation",
                              validate=mmValidate.OneOf(["set"]))
    value = fields.Boolean(required=True, description="The attribute value")

class CertsBatchRevoke(Schema):
    ids = fields.List(fields.Integer, required=True, description="The certificated ids to be revoked/unrevoked")
    revokeValue = fields.Boolean(default=True, missing=True, description="The certificates' revokation value")

from flask_restx.model import Model
g_certModelOut: Model = g_theApi.model("Output certificate model",
    {"id": FlaskRestPlusFields.Integer(description="certificate's id"),
     **ModelFromSchema(CertSchema)
    })

g_certsModel: Model = g_theApi.model("Certificates model",
                {
                    "pagination" : FlaskRestPlusFields.Boolean(required=True, description="States if pagination is enabled or not"),
                    "total_items" : FlaskRestPlusFields.Integer(description="Total number of items in the collection. Missing if pagination is False"),
                    "page" : FlaskRestPlusFields.Integer(description="The page number. Missing if pagination is False"),
                    "per_page" : FlaskRestPlusFields.Integer(description="Per page items no. Missing if pagination is False"),
                    "certs" : FlaskRestPlusFields.List(FlaskRestPlusFields.Nested(g_certModelOut),
                                                                        description="certificates list")
                })

# noinspection PyUnresolvedReferences
@g_theApi.route("/certs", )
class Certs(JWTAuthResource):
    """
        The certificates rest resource
    """

    # @g_theApi.marshal_with(g_certsModel, skip_none=True)
    def get(self):
        """
            Gets the certificates list
        :return: a paged/unpaged list of certificates
        """
        # from Utils.CertsUtils import GetCertAndKey
        # cert, key = GetCertAndKey(g_theApi.app, 1, 1)
        from flask import request as req
        from Api.OvpnConfigTemplates.Utils import ConfigFromReqArgs, DateTimeFromStr
        from datetime import datetime

        config = ConfigFromReqArgs(req.args, [
            {
              "name": "all",
              "default": False
            },
            {
                "name": "date",
                "type": str,
                "post": DateTimeFromStr,
                "default": datetime.now()
            },
            {
                "name": "includePEM",
                "default": False
            }
        ])

        from sqlalchemy import func

        if not config["all"]:
            subq = g_theApi.app.Db().session.query(
                CertsDbModel.id,
                func.row_number().over(partition_by=[CertsDbModel.entityId, CertsDbModel.orgId],
                                       order_by=CertsDbModel.id.desc()).label('rowNoWithinPartition')).\
                subquery(name="lastCerts") #Note: "row_number" was introduced in sqlite3 3.25 so use a python newer enough
            query = CertsDbModel.query.join(subq, CertsDbModel.id == subq.c.id).filter(subq.c.rowNoWithinPartition == 1)
        else:
            query = CertsDbModel.query
        res =  ResourcesUtils.Get(CertsDbModel, {
            "query": query
        })

        from flask_restx import marshal
        resDict = marshal(res, g_certsModel, skip_none=True)

        for idx, certEntry in enumerate(resDict["certs"]):
            certEntry["state"] = str(CertsUtils.StateFromCertDbObj(res["certs"][idx], config).name).lower() \
                if not certEntry["revoked"] else "revoked"
            del(certEntry["revoked"])
        if config["includePEM"]:
            for idx, certEntry in enumerate(resDict["certs"]):
                certEntry["certPEM"] = res["certs"][idx].cert.decode().rstrip()
        return resDict

@g_theApi.route("/certs:batchRevoke")
class CertsBatchRevoke(JWTAuthResource):
    @g_theApi.expect(g_theApi.model("Certificates batch revoke", ModelFromSchema(CertsBatchRevoke)))
    def post(self):
        revokeCertsIds = g_theApi.payload["ids"]
        if len(revokeCertsIds) == 0:
            return {"message": "No certificates ids provided"}, 400
        revokeValue = g_theApi.payload.get("value", True)
        try:
            CertsDbModel.query.filter(CertsDbModel.id.in_(revokeCertsIds)).update({"revoked": revokeValue},
                                                                                  synchronize_session=False)
            g_theApi.app.Db().session.commit()
            return None, 200
        except Exception as e:
            abort(500, str(e))

@g_theApi.route("/certs/<int:certId>", doc={"params": {"id": "certificate's id"}})
class CertsId(JWTAuthResource):
    """
        The per id certificate rest resource
    """

    @g_theApi.marshal_with(g_certModelOut, skip_none=True)
    def get(self, certId):
        """
            Gets a specific certificate

        :param certId: the certificate's id
        :return: the certificate object or aborts with 4xx/5xx http status and an error json
        """
        return ResourcesUtils.GetSingle(CertsDbModel, certId)

    @g_theApi.expect(g_theApi.model("Certificate patch model", ModelFromSchema(CertPatchSchema)))
    def patch(self, certId):
        """
            Patch certificate record.

            The payload json fields are:
                * attr [required]: the attribute to be patched. Currently only "revoked" attribute is supported
                * operation [optional]: the operation to be performed. Currently only "set" attribute is supported
                * value [required]: the value to be set to the attribute. For "revoked" only "True" or "False" values are allowed

        :param certId: certificate id
        :return: http status 200 or aborts with 4xx/5xx http status and an error json
        """
        from Database.Models import CertsDbModel
        from sqlalchemy.orm.exc import NoResultFound

        try:
            certObj: CertsDbModel = CertsDbModel.query.filter(CertsDbModel.id == certId).one()
            patchData = g_theApi.payload
            certObj.revoked = patchData["value"]
            g_theApi.app.Db().session.commit()

            return None, 200
        except NoResultFound:
            abort(400, "Certificate id not found")
