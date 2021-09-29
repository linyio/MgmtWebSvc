from flask_restx import fields as FlaskRestPlusFields
from Api import g_theApi, EntityLikeSchemaBase
from Database.Models import EntityDbModel, OrgDbModel, EntityOrgBindings, EntityTypeEnum, ServersExtraInfoDbModel
from marshmallow import Schema, fields, post_load, validate as mmValidate, post_dump
from Utils.ModelUtils import ModelFromSchema, ValidRelationshipIds
from Utils import ResourcesUtils
from Utils.ResourcesUtils import JWTAuthResource
from Utils.SettingsUtils import EnvOrSetting


class EntitySchema(EntityLikeSchemaBase):
    _entityName = "entity"
    typeId = fields.Integer(required=True,
                            description=_entityName.capitalize() + ' type id')

    @post_load
    def CreateEntity(self, data, **kwargs):
        return EntityDbModel(**data)

from flask_restx.model import Model

# build flask_restx model out of marshmallow schema, for using it with @api.marshal_with decorator
g_entityModelIn: Model = g_theApi.model("Input entity (user/server) model",
                                        ModelFromSchema(EntitySchema))
                                        # ModelFromSchema(EntitySchema, g_entitySchemaNestedFieldsMapping))

g_entityModelOut: Model = g_theApi.model("Output entity (user/server) model",
                                         {"id": FlaskRestPlusFields.Integer(
                                             description='The unique identifier of an entity'),
                                             **ModelFromSchema(EntitySchema)})
                                             # **ModelFromSchema(EntitySchema, g_entitySchemaNestedFieldsMapping)})

g_entityModel = g_theApi.model("Entity model",
                               {
                                   "pagination": FlaskRestPlusFields.Boolean(required=True,
                                                                             description="States if pagination is enabled or not"),
                                   "total_items": FlaskRestPlusFields.Integer(
                                       description="Total number of items in the collection. Missing if pagination is False"),
                                   "page": FlaskRestPlusFields.Integer(
                                       description="The page number. Missing if pagination is False"),
                                   "perPage": FlaskRestPlusFields.Integer(
                                       description="Per page items no. Missing if pagination is False"),
                                   "entities": FlaskRestPlusFields.List(FlaskRestPlusFields.Nested(g_entityModelOut),
                                                                        description="Entities list")
                               })

@g_theApi.route("/entities")
class Entities(JWTAuthResource):
    """
        The Entities
    """

    # @g_theApi.marshal_with(g_entityModel, skip_none=True)
    def get(self):
        """
            Gets the entities list
        :return: the entities list
        """
        res = ResourcesUtils.Get(EntityDbModel, {
            "page": ResourcesUtils.ReqSafeArg("page", 0),
            "perPage": ResourcesUtils.ReqSafeArg("perPage", 10),
            "limit": EnvOrSetting("LIMIT_ENTITIES", None, 1000)
        })

        from flask_restx import marshal
        resDict = marshal(res, g_entityModel, skip_none=True)

        from flask import request as req

        if "withOrgs" in req.args and req.args["withOrgs"].lower() in ["1", "on", "true"]:  # add associated orgs ids to each user
            for idx, entity in enumerate(res["entities"]):
                resDict["entities"][idx]["orgsIds"] = [org.id for org in entity.orgs]

        return resDict

    # @g_theApi.expect(g_entityModelWithOrgsIdsIn)
    @g_theApi.expect(g_entityModelIn)
    def post(self):
        """
            Creates a new entity based on the json from payload
        :return: 201 http status with no message or aborts with 400/500 http status and an error json
        """

        class Callbacks:
            m_orgsIds = []

            def PreLoad(self, entityDict):
                if not "orgsIds" in entityDict:
                    return False, {
                        "retMsg": "Missing 'orgsIds' field",
                        "httpStatus": 400
                    }
                elif type(entityDict["orgsIds"]) != list or len(entityDict["orgsIds"]) == 0:
                    return False, {
                        "retMsg": "'orgsIds' field must be a non-empty array",
                        "httpStatus": 400
                    }

                orgsIds = frozenset(entityDict["orgsIds"])
                validEntitiesIds, resDict = ValidRelationshipIds(orgsIds, OrgDbModel)
                if validEntitiesIds:
                    self.m_orgsIds = orgsIds
                    return True, {}
                else:
                    return False, {
                        "retMsg": f"Invalid organization id '{resDict['invalidId']}'",
                        "httpStatus": 400
                    }

            def PreAdd(self, entity: EntityDbModel):
                if entity.typeId == EntityTypeEnum.server:
                    entity.srvExtraInfo = ServersExtraInfoDbModel(tlsKey=b"")
                dbSession = g_theApi.app.Db().session
                for org in OrgDbModel.query.filter(OrgDbModel.id.in_(self.m_orgsIds)):
                    org.entities.append(entity)
                dbSession.commit()

                return False, {  # force the exit. The entity was already added due to the relationship setup
                    "retMsg": {
                        "id": entity.id
                    },
                    "httpStatus": 201
                }

        return ResourcesUtils.Post(g_theApi, EntitySchema(unknown="EXCLUDE"), {
            "limit": EnvOrSetting("LIMIT_ENTITIES", None, 100000),
            "callbacks": Callbacks()
        })


@g_theApi.route("/entities/<int:entityId>", doc={"params": {"entityId": "the entity id"}})
class EntityId(JWTAuthResource):
    """
            The per id Entitys rest resource
    """

    @g_theApi.marshal_with(g_entityModelOut, skip_none=True)
    def get(self, entityId):
        """
            Gets a specific entity

        :param entityId: the entity id
        :return: the Entity object or aborts with 400/500 http status and an error json
        """
        return ResourcesUtils.GetSingle(EntityDbModel, entityId)

    @g_theApi.expect(g_entityModelIn, validate=False)
    def patch(self, entityId):
        """
            Patch an entity with the info from json from payload

        :return: 200 http status with no message if succeeded or aborts with 400/500 http status and an error json
        """

        class Callbacks:
            m_orgsIdsPatch = {}
            # m_newAssocServiceId = None

            def PreUpdate(self, entityPatchReqDict):
                # validate and record the entities ids operations
                from Utils.Misc import CheckPatchRelationshipCollection
                validPatchCollection, result = CheckPatchRelationshipCollection(entityPatchReqDict, "orgsIds", {
                    "collectionItemsName": "org",
                    "deleteCollection": True
                })
                if validPatchCollection:
                    if result["collectionFound"]:
                        self.m_orgsIdsPatch = result["validatedCollection"]
                    return (True, {}) \
                        if "add" in self.m_orgsIdsPatch or not "remove" in self.m_orgsIdsPatch or \
                           self.m_orgsIdsPatch["remove"] != \
                           frozenset([row.orgId for row in EntityOrgBindings.query.
                                     with_entities(EntityOrgBindings.orgId).filter(
                               EntityOrgBindings.entityId == entityId)]) \
                        else (False, {
                        "retMsg": f"The patch operation would remove all associated organization",
                        "httpStatus": 400
                    })
                else:
                    return False, result

            def PostUpdate(self):
                from Utils.Misc import DoPatchRelationshipOperations
                DoPatchRelationshipOperations(self.m_orgsIdsPatch, g_theApi.app.Db().session, EntityOrgBindings,
                                              EntityOrgBindings.entityId, EntityOrgBindings.orgId, entityId,
                                              lambda operationItemId:
                                              EntityOrgBindings(orgId=operationItemId, entityId=entityId))

                return True, {}

        return ResourcesUtils.Patch(g_theApi, EntitySchema(unknown="EXCLUDE"), EntityDbModel, entityId, {
            "callbacks": Callbacks()
        })

    @g_theApi.response(204, 'Entity successfully deleted.')
    def delete(self, entityId):
        """
            Deletes an entity

        :param entityId: the entity id
        :return: http status 200 or aborts with 400/500 http status and an error json
        """
        return ResourcesUtils.Delete(g_theApi, EntityDbModel, entityId)


@g_theApi.route("/entities:batchDelete")
class EntitiesBatchDelete(JWTAuthResource):
    def post(self):
        from Utils.ResourcesUtils import BatchDelete
        return BatchDelete(g_theApi, EntityDbModel)


from Api.Orgs import g_orgsModel


@g_theApi.route("/entities/<int:entityId>/orgs", doc={"params": {"entityId": "the entity id"}})
class EntitiesOrgs(JWTAuthResource):
    """
                The entity - organization binding rest resource,
    """

    @g_theApi.marshal_with(g_orgsModel, skip_none=True)
    def get(self, entityId):
        """
            Gets the orgs list to which a specific entity is bound (associated) with

        :param entityId: the entity id
        :return: the orgs list or aborts with 400/500 http status and an error json
        """
        entity = ResourcesUtils.GetSingle(EntityDbModel, entityId)
        return ResourcesUtils.GetFromQuery(entity.orgs, {
            "page": ResourcesUtils.ReqSafeArg("page", 0),
            "perPage": ResourcesUtils.ReqSafeArg("perPage", 10)})

    class EntityOrgsPatchSchema(Schema):
        attr = fields.String(required=True, description="The attribute to be modified",
                             validate=mmValidate.OneOf(["orgs"]))
        operation = fields.String(required=True, description="The operation",
                                  validate=mmValidate.OneOf(("add", "del")))
        value = fields.String(required=True, description="The attribute value")

    @g_theApi.expect(g_theApi.model("Entity - orgs patch model", ModelFromSchema(EntityOrgsPatchSchema)))
    def patch(self):
        """
            Patch  entities's orgs list by adding/removing an org binding to/from an entity

        :param entityId: the entity id
        :return: http status 200 or aborts with 400/500 http status and an error json
        """
        from Database.Models import OrgDbModel
        from sqlalchemy.orm.exc import NoResultFound
        from flask_restx import abort

        try:
            return ResourcesUtils.PatchRelatedModel(g_theApi, EntityDbModel, OrgDbModel, self.EntityOrgsPatchSchema(),
                                                    entityId, "orgs")
        except NoResultFound:
            abort(400, "Organization or entity not found")
