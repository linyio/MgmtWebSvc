from flask_restx import fields as FlaskRestPlusFields
from Api import EntityLikeSchemaBase, g_theApi
from Database.Models import OrgDbModel, EntityDbModel, EntityOrgBindings
from marshmallow import Schema, fields, post_load, validate as mmValidate
from Utils.ModelUtils import ModelFromSchema, ValidRelationshipIds
from Utils import ResourcesUtils

# Orgs marshmallow schema
from Utils.ResourcesUtils import JWTAuthResource
from Utils.SettingsUtils import EnvOrSetting


class OrgSchema(EntityLikeSchemaBase):
    _entityName = "org"

    @post_load
    def CreateOrg(self, data, **kwargs):
        return OrgDbModel(**data)


from flask_restx.model import Model

# build flask_restx model out of marshmallow schema, for using it with @api.marshal_with decorator
g_orgModelIn: Model = g_theApi.model("Input org model",
                                     ModelFromSchema(OrgSchema))

g_orgModelOut: Model = g_theApi.model("Output org model",
                                      {"id": FlaskRestPlusFields.Integer(
                                          description='The unique identifier of an organization'),
                                          **ModelFromSchema(OrgSchema)})

g_orgsModel: Model = g_theApi.model("Orgs model",
                                    {
                                        "pagination": FlaskRestPlusFields.Boolean(required=True,
                                                                                  description="States if pagination is enabled or not"),
                                        "total_items": FlaskRestPlusFields.Integer(
                                            description="Total number of items in the collection. Missing if pagination is False"),
                                        "page": FlaskRestPlusFields.Integer(
                                            description="The page number. Missing if pagination is False"),
                                        "perPage": FlaskRestPlusFields.Integer(
                                            description="Per page items no. Missing if pagination is False"),
                                        "orgs": FlaskRestPlusFields.List(FlaskRestPlusFields.Nested(g_orgModelOut),
                                                                         description="Organizations list")
                                    })


@g_theApi.route("/orgs")
class Orgs(JWTAuthResource):
    """
        The Orgs rest resource

        Optionally, it supports pagination, through query strings, as following:
            * page: the page number
            * perPage: the items number of a page
    """

    # @g_theApi.marshal_with(g_orgsModel, skip_none=True)
    def get(self):
        """
            Gets the orgs list

        :return: the organizations list
        """
        res = ResourcesUtils.Get(OrgDbModel, {
            "page": ResourcesUtils.ReqSafeArg("page", 0),
            "perPage": ResourcesUtils.ReqSafeArg("perPage", 10),
            "limit": EnvOrSetting("LIMIT_ORGS", None, 1000)
        })

        from flask_restx import marshal
        resDict = marshal(res, g_orgsModel, skip_none=True)

        from flask import request as req

        if "withEntities" in req.args and req.args["withEntities"].lower() in ["1", "on", "true"]:  # add associated orgs ids to each user
            for idx, org in enumerate(res["orgs"]):
                orgQuery = org.entities
                if "entitiesOrderBy" in req.args and hasattr(EntityDbModel, req.args["entitiesOrderBy"]):
                    orgQuery = orgQuery.order_by(getattr(EntityDbModel, req.args["entitiesOrderBy"]))
                resDict["orgs"][idx]["entitiesIds"] = [entity.id for entity in orgQuery]

        return resDict

    @g_theApi.expect(g_orgModelIn)
    def post(self):  # Todo: check for duplicates
        """
            Creates a new organization based on the json from payload

        :return: 201 http status with no message or aborts with 400/500 http status and an error json
        """

        class Callbacks:
            m_entitiesIds = []

            def PreLoad(self, orgReqDict):
                if "entitiesIds" in orgReqDict:
                    if type(orgReqDict["entitiesIds"]) != list:
                        return False, {
                            "retMsg": "'entitiesIds' field must be array",
                            "httpStatus": 400
                        }
                else:
                    return True, {}  # no entitiesIds - just return
                entitiesIds = frozenset(orgReqDict["entitiesIds"])
                validEntitiesIds, resDict = ValidRelationshipIds(entitiesIds, EntityDbModel)
                if validEntitiesIds:
                    self.m_entitiesIds = entitiesIds
                    return True, {}
                else:
                    return False, {
                        "retMsg": f"Invalid entity id '{resDict['invalidId']}'",
                        "httpStatus": 400
                    }

            def PreAdd(self, org):
                if len(self.m_entitiesIds) == 0:
                    return True, {}
                for entity in EntityDbModel.query.filter(EntityDbModel.id.in_(self.m_entitiesIds)):
                    entity.orgs.append(org)
                g_theApi.app.Db().session.commit()

                return False, {  # force the exit. The entity was already added due to the relationship setup
                    "retMsg": {
                        "id": org.id
                    },
                    "httpStatus": 201
                }

        return ResourcesUtils.Post(g_theApi, OrgSchema(unknown="EXCLUDE"), {
            "limit": EnvOrSetting("LIMIT_ORGS", None, 1000),
            "callbacks": Callbacks()
        })


@g_theApi.route("/orgs/<int:orgId>", doc={"params": {"orgId": "the organization id"}})
class OrgsId(JWTAuthResource):
    """
        The per id Orgs rest resource
    """

    @g_theApi.marshal_with(g_orgModelOut, skip_none=True)
    def get(self, orgId):
        """
            Gets a specific organization

        :param orgId: the organizaton id
        :return: the Org object or aborts with 400/500 http status and an error json
        """
        # return ResourcesUtils.GetSingle(OrgDbModel, orgId)
        return ResourcesUtils.GetOrg(orgId)

    @g_theApi.expect(g_orgModelIn, validate=False)
    def patch(self, orgId):
        """
            Patch an organization with the info from json from payload

        :return: 200 http status with no message if succeeded or aborts with 400/500 http status and an error json
        """

        class Callbacks:
            m_entitiesIdsPatch = {}

            def PreUpdate(self, orgPatchReqDict):
                # validate and record the entities ids operations
                from Utils.Misc import CheckPatchRelationshipCollection
                validPatchCollection, result = CheckPatchRelationshipCollection(orgPatchReqDict, "entitiesIds", {
                    "collectionItemsName": "entity",
                    "deleteCollection": True
                })
                if validPatchCollection:
                    if result["collectionFound"]:
                        if "remove" in result["validatedCollection"] and \
                                EntityOrgBindings.query.with_entities(EntityOrgBindings.entityId). \
                                        filter(EntityOrgBindings.entityId.in_(result["validatedCollection"]["remove"])). \
                                        count() < len(result["validatedCollection"]["remove"]) * 2:
                            return False, {
                                "retMsg": "Attempt to remove the sole organization for at least one entity",
                                "httpStatus": 400
                            }
                        else:
                            self.m_entitiesIdsPatch = result["validatedCollection"]
                    return True, {}
                else:
                    return False, result

            def PostUpdate(self):
                from Utils.Misc import DoPatchRelationshipOperations
                DoPatchRelationshipOperations(self.m_entitiesIdsPatch, g_theApi.app.Db().session, EntityOrgBindings,
                                              EntityOrgBindings.orgId, EntityOrgBindings.entityId, orgId,
                                              lambda operationItemId:
                                              EntityOrgBindings(orgId=orgId, entityId=operationItemId))

                return True, {}

        return ResourcesUtils.Patch(g_theApi, OrgSchema(unknown="EXCLUDE"), OrgDbModel, orgId, {
            "callbacks": Callbacks()
        })

    @g_theApi.response(204, 'Org successfully deleted.')
    def delete(self, orgId):
        """
            Deletes an organization

        :param orgId:  the organizaton id
        :return: http status 200 or aborts with 400/500 http status and an error json
        """
        return ResourcesUtils.Delete(g_theApi, OrgDbModel, orgId)


@g_theApi.route("/orgs:batchDelete")
class OrgsBatchDelete(JWTAuthResource):
    def post(self):
        from Utils.ResourcesUtils import BatchDelete
        return BatchDelete(g_theApi, OrgDbModel)


from Api.Entities import g_entityModel


@g_theApi.route("/orgs/<int:orgId>/entities", doc={"params": {"orgId": "the organization id"}})
class OrgsEntities(JWTAuthResource):
    """
        The organization - entity binding rest resource
    """

    @g_theApi.marshal_with(g_entityModel, skip_none=True)
    def get(self, orgId):
        """
            Gets the entities' list bound to (associated with) a specific organization

        :param orgId: the organization id
        :return: the ursers list or aborts with 400/500 http status and an error json
        """
        org = ResourcesUtils.GetSingle(OrgDbModel, orgId)
        return ResourcesUtils.GetFromQuery(org.entities, {
            "page": ResourcesUtils.ReqSafeArg("page", 0),
            "perPage": ResourcesUtils.ReqSafeArg("perPage",
                                                 10)})  # ToDo: determine if shall we return just the urls instead of full objects?!

    class OrgEntitiesPatchSchema(Schema):
        """
            The org - entity binding marshmallow schema used for pathing (adding/removing)
        """
        attr = fields.String(required=True,
                             description='The attribute to be modified. For now only "entities" is accepted',
                             validate=mmValidate.OneOf(["entities"]))
        operation = fields.String(required=True,
                                  description='The operation. For now only "add" and "del" operations are accepted',
                                  validate=mmValidate.OneOf(("add", "del")))
        value = fields.String(required=True, description="The attribute value")

    @g_theApi.expect(g_theApi.model("Org - entities patch model", ModelFromSchema(OrgEntitiesPatchSchema)))
    def patch(self, orgId):
        """
            Patch organization's entities list by adding/removing an entity to/from an organization

        :param orgId: the organization id
        :return: http status 200 or aborts with 400/500 http status and an error json
        """
        from Database.Models import EntityDbModel
        from sqlalchemy.orm.exc import NoResultFound
        from flask_restx import abort

        try:
            return ResourcesUtils.PatchRelatedModel(g_theApi, OrgDbModel, EntityDbModel, self.OrgEntitiesPatchSchema(),
                                                    orgId, "entities")
        except NoResultFound:
            abort(400, "Organization or entity not found")
