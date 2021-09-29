from marshmallow.exceptions import ValidationError
from flask_restx import abort
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.orm.exc import NoResultFound

from Utils.Misc import MergeConfigs

def ReqSafeArg(arg, defaultValue):
    from flask import request
    from Utils.Misc import DictGetSafe

    return DictGetSafe(request.args, arg, defaultValue)

_getListDefaultConfig = {
    "page": 0, #if set to a negative value then there will be no pagination reference in the output object
    "perPage": 10,
    "orderByColumn": "orderBy" #if string then the column name is retrieved from http request object, otherwise it must
                                # represent a flask column object
}

def Get(model, config = None):
    """
        Helper function for retrieving the entire or a page of a list of objects as result of a get resource

    :param model: the model used for query
    :param config: config
    :return: a dictionary of objects reflecting the model
    """
    config = MergeConfigs(config, _getListDefaultConfig)
    orderByColumn = config["orderByColumn"]
    if type(orderByColumn) is str :
        from flask import request as req
        orderByColumn = getattr(model, req.args[orderByColumn]) if orderByColumn in req.args and \
                           hasattr(model, req.args[orderByColumn]) else None
    query = config.get("query" ,model.query)
    if not orderByColumn is None:
        query = query.order_by(orderByColumn)
    if "limit" in config and type(config["limit"] is int):
        query = query.limit(config["limit"])
    return GetFromQuery(query, config)

def GetFromQuery(query, config = None):
    config = MergeConfigs(config, _getListDefaultConfig)
    page = config["page"]
    perPage = config["perPage"]
    collectionName = config["collectionName"] if "collectionName" in config else \
        query.column_descriptions[0]['type'].__tablename__
    if "columns" in config and type (config["columns"]) == list:
        query = query.with_entities(*config["columns"])
    if page != 0:
        from flask_sqlalchemy import Pagination
        pagObj: Pagination = query.paginate(page, perPage, error_out=False)
        return {"pagination": True, "total_items": pagObj.total, "page": pagObj.page, "perPage": pagObj.per_page,
                collectionName: pagObj.items}
    else:
        return {
            **({"pagination": False} if page > 0 else {}),
            collectionName: query.all()
        }

def GetSingle(model, recordId):
    try:
        return model.query.filter(model.id == recordId).one()
    except ValidationError as e:
        abort(400, f"Validation error - {e}")
    except NoResultFound:
        abort(400, f"The object id {recordId} was not found")
    except Exception as e:
        abort(500, f"Error - {e}")

def CallCallback(callbacksInst, callbackName, config, *callbackArgs):
    if not callbacksInst is None: #if collbackInst is not None then it's assumed to be a callbacks class
        if hasattr(callbacksInst, callbackName):
            return getattr(callbacksInst, callbackName)(*callbackArgs)
    elif callbackName in config:
        callback = config[callbackName]
        if callable(callback):
            return callback(*callbackArgs)
    return True, {}

def ParseCallbackResult(callbackResult, callbackName, defaultRetMsg = None, defaultHttpStatus = 500):
    retMsg = defaultRetMsg if not defaultRetMsg is None else {
        "message": f"Error {callbackName} callback call"
    }
    if "retMsg" in callbackResult:
        retMsg = {
            "message": callbackResult["retMsg"]
        } if type(callbackResult["retMsg"]) is str else callbackResult["retMsg"] if \
            type(callbackResult["retMsg"]) is dict or callbackResult["retMsg"] is None else{
            "message": f"invalid 'err' field type in {callbackName} callback call. Expected 'str', 'None' or 'dict'"
        }
    return retMsg, callbackResult["httpStatus"] if "httpStatus" in callbackResult and type(callbackResult["httpStatus"]) == int else defaultHttpStatus

def Post(apiObj, schema, config=None):
    """
        Helper function for creating an object as data of a post resource

    :param apiObj: the api object
    :param schema: the schema used to load the input data
    :return: None, 201 if OK or raise a ValidationError exception otherwise
    """
    _defaultPostConfig = {
        "limit": None
    }

    data = apiObj.payload
    obj = None
    try:
        config = MergeConfigs(config, _defaultPostConfig)
        # continueLoad, data = CallHook(config["preLoad"], data)

        callbacksInst = config["callbacks"] if "callbacks" in config else None
        continueLoad, result = CallCallback(callbacksInst, "PreLoad", config, data)
        if not continueLoad:
            return ParseCallbackResult(result, "PreLoad")
        elif "result" in result:
            data = result["result"]

        obj = schema.load(data)
        dbSession = apiObj.app.Db().session

        limit = config["limit"]
        if type(limit) == int and obj.query.count() >= limit:
            return {"message": f"The {obj.__kinds__ if hasattr(obj, '__kinds__') else 'records'} number limit reached"
                if not "limitErrorMessage" in config else config["limitErrorMessage"]}, 500

        continueAdd, result = CallCallback(callbacksInst, "PreAdd", config, obj)
        if not continueAdd:
            return ParseCallbackResult(result, "PreAdd")
        elif "result" in result:
            obj = result["result"]

        dbSession.add(obj)
        dbSession.commit()

        continuePost, result = CallCallback(callbacksInst, "PostAdd", config, obj)
        if not continuePost:
            return ParseCallbackResult(result, "PostAdd")
        elif "result" in result:
            obj = result["result"]

        return {"id": obj.id}, 201 #make sure the obj (i.e. SQLAlchemy row) will always have an id column
    except ValidationError as e:
        abort(400, f"Validation error - {e}")
    except IntegrityError as e:
        if "UNIQUE constraint failed" in e.args[0]:
            abort(400, obj.PrettyRepr() + " aready exists")
        abort(500, f"Error - {e}")
    except Exception as e:
        abort(500, f"Error - {e}")
    return 500, None

def Patch(apiObj, schema, model, recordId, config=None):
    """
        Helper function for patching an existing object as result of a patch resource

    :param apiObj: the api object
    :param schema: the schema used to load the input data
    :return: None, 204 if OK or raise a ValidationError exception otherwise
    """
    # _defaultPatchConfig = {
    #     "preLoad": None,
    #     "preUpdate": None,
    #     # "postPost": None,
    #     "limit": None
    # }

    data = apiObj.payload
    try:
        if config is None:
            config = {}
        callbacksInst = config["callbacks"] if "callbacks" in config else None

        continueLoad, result = CallCallback(callbacksInst, "PreUpdate", config, data)
        if not continueLoad:
            return ParseCallbackResult(result, "PreUpdate")
        elif "result" in result:
            data = result["result"]
        # obj = schema.load(data, partial = True)
        #
        # continuePreUpdate, result = CallCallback(callbacksInst, "PreUpdate", config, obj)
        # if not continuePreUpdate:
        #     return ParseCallbackResult(result, "PreUpdate")
        # elif "result" in result:
        #     obj = result["result"]

        if len(data):
            model.query.filter(model.id == recordId).update(data)
            # model.query.filter(model.id == recordId).update(obj)
            apiObj.app.Db().session.commit()

        continuePosUpdate, result = CallCallback(callbacksInst, "PostUpdate", config)
        if not continuePosUpdate:
            return ParseCallbackResult(result, "PostUpdate")
        # elif "result" in result:
        #     obj = result["result"]

    except ValidationError as e:
        return f"Validation error - {e}", 400
    except Exception as e:
        return f"Error - {e}", 500

    return None, 204

def Put(apiObj, schema, model, recId):
    """
        Helper function for updating an object as result of a put resource

    :param apiObj: the api object
    :param schema: the schema used to load the input data
    :param model: the model used for identifying the object to be modified
    :param recId: the object id within model
    :return: None, 204 if OK or raise a ValidationError exception otherwise
    """
    data = apiObj.payload
    try:
        obj = schema.load(data)
        modelObj = model.query.filter(model.id == recId).one()
        # noinspection PyProtectedMember
        for fieldName in schema._declared_fields.keys():
            setattr(modelObj, fieldName, getattr(obj, fieldName))
        db = apiObj.app.Db()
        db.session.add(modelObj)
        db.session.commit()
    except ValidationError as e:
        abort(400, f"Validation error - {e}")
    except NoResultFound:
        abort(400, f"The object id {recId} was not found")
    except Exception as e:
        abort(500, f"Error - {e}")

    return None, 204

def Delete(apiObj, model, recId):
    """
        Helper function for deleting an object as result of a delete resource

    :param apiObj: the api object
    :param model: the model used for identifying the object to be deleted
    :param recId: the object id within model
    :return: None, 200
    """
    try:
        db = apiObj.app.Db()
        db.session.delete(model.query.filter(model.id == recId).one())
        db.session.commit()
        return None, 200
    except ValidationError as e:
        abort(400, f"Validation error - {e}")
    except NoResultFound:
        abort(400, f"The object id {recId} was not found")
    except Exception as e:
        abort(500, f"Error - {e}")

def BatchDelete(apiObj, model):
    """
        Helper function for deleting multiple objects

    :param apiObj: the api object
    :param model: the model used for identifying the object to be deleted
    :return: None, 200
    """

    try:
        ids = apiObj.payload["ids"]
        model.query.filter(model.id.in_(ids)).delete(synchronize_session=False)
        # model.__table__.delete().where(model.id.in_(ids))
        db = apiObj.app.Db()
        # db.session.delete(model.query.filter(model.id in ids))
        db.session.commit()
        return None, 200
    except KeyError as e:
        abort(400, f'Missing "{e.args[0]}" field')
    except Exception as e:
        abort(500, f"Error - {e}")

def PatchRelatedModel(apiObj, model, relatedModel, schema, modelId, modelRelatedFieldName):
    """
        Patch a model by appending/removing an element from second related model

    :param apiObj:  the api object
    :param model: the model used for identifying the object to be deleted
    :param relatedModel: the related model from which the element is added/removed
    :param schema: the patch schema from which the data is loaded
    :param modelId: the model id which gets patched
    :param modelRelatedFieldName: the model filed name which describe the relationship with the second model
    :return: None, 200 if OK ar raise an exception otherwise
    """
    try:
        data = schema.load(apiObj.payload)
        db = apiObj.app.Db()
        modelObj = model.query.filter(model.id == modelId).one()
        modelRelatedField = getattr(modelObj, modelRelatedFieldName)
        if data["operation"] == "add":
            # add operation
            modelRelatedObj = relatedModel.query.filter(relatedModel.id == data["value"]).one()
            modelRelatedField.append(modelRelatedObj)
            db.session.commit()
        elif data["operation"] == "del":
            # delete operation
            modelRelatedObj = modelRelatedField.filter(relatedModel.id == data["value"]).one() #search the related id
            modelRelatedField.remove(modelRelatedObj)
            db.session.commit()
        else:
            abort(400, f'Invalid operation - {data["operation"]}')
    except (ValidationError, DatabaseError) as e:
        abort(400, f"Validation error - {e}")
    return None, 200

g_entitiesTypesMapById = None

def EntityType(entityTypeId) -> str:
    global g_entitiesTypesMapById
    if g_entitiesTypesMapById is None:
        from Database.Models import EntityTypeDbModel
        # for entityType in EntityTypeDbModel.query:
        #     g_entitiesTypesMapById[entityType.id] = entityType
        g_entitiesTypesMapById = {
            entityType.id: entityType.name.name for entityType in  EntityTypeDbModel.query
        }
    return g_entitiesTypesMapById[entityTypeId]

def GetOrg(orgId):
    from Database.Models import OrgDbModel
    return GetSingle(OrgDbModel, orgId)

def GetEntity(entityId):
    from Database.Models import EntityDbModel
    entity = GetSingle(EntityDbModel, entityId)
    return entity, EntityType(entity.typeId)

from flask_restx import Resource
from functools import wraps

def JwtAuth(httpMethod):
    @wraps(httpMethod)
    def wrapper(*args, **kwargs):
        from flask import request
        if not "Authorization" in request.headers:
            abort(401, "Missing authentication header")
        if not request.headers["Authorization"].startswith("Bearer ") or \
            len(request.headers["Authorization"]) == 7: #the string is just "Bearer "
            abort(401, "Malformed authentication header")
        encodedReqJwt = request.headers["Authorization"].split()[1]

        import jwt

        reqJwtHeaders = jwt.get_unverified_header(encodedReqJwt)
        if "alg" not in reqJwtHeaders and reqJwtHeaders["alg"] != "ES512" or\
            "typ" not in reqJwtHeaders and reqJwtHeaders["typ"] != "JWT" or \
            "kid" not in reqJwtHeaders and reqJwtHeaders["kid"] != "lxTkvONAr97dOiitHFVP4-6KHxZIqGfXNC11c6Q-OIU":
            abort(401, "Invalid JWT headers")
        reqJwt = {}
        try:
            reqJwt = jwt.decode(encodedReqJwt, """-----BEGIN PUBLIC KEY-----
MIGbMBAGByqGSM49AgEGBSuBBAAjA4GGAAQBbt1qDq8dkPg2KAyDW6eiI0kxotiFukwN3x6lfzPCRXkgk00qzExAlu60f6dS9Rn8B3Dz91LoFtxm++z+W7ztI7cALJao3yVGqhZ/Q6xxPy7HOA1u2qn2YZOinf6HYDydLeoGbaeKJgBGqu/FmImlDOsz/R5xABlNZyJtjlQklNa/nho=
-----END PUBLIC KEY-----
""",                                ["ES512"], {
                                    "verify_signature": True,
                                    "verify_aud": False,
                                    "required": ["exp", "iat", "sub"]
                                }, issuer="https://www.liny.io/auth/realms/liny")
        except Exception as e:
            abort(401, "Error decoding/authenticating JWT - " + str(e))

        #ToDO: check "allowed-origins"?!
        from Api import g_theApi
        if not reqJwt["sub"] in g_theApi.app.config["USER_IDS"]:
            abort(401, "Invalid JWT subject")
        request.jwt = reqJwt
        return httpMethod(*args, **kwargs)
    return wrapper

class JWTAuthResource(Resource):
    method_decorators = [JwtAuth]
