def DictGetSafe(inDict, key, defaultValue=None):
    result = defaultValue
    try:
        result = type(defaultValue)(inDict[key])
    except (ValueError, KeyError):
        pass
    return result

def RecordExists(recordName, recordValue, config=None):
    defaultRecordExistsConfig = {
        "recordName": "record",
        # "errorMessage": 'Organization "%s" already exists'
    }
    if config is None:
        config = defaultRecordExistsConfig
    elif type(config) is dict:
        config = {**defaultRecordExistsConfig, **config}
    from sqlalchemy import exists

    from Api import g_theApi
    db = g_theApi.app.Db()
    return (True, None) if not db.session.query(exists().where(recordName == recordValue)).scalar() \
        else (False, config["errorMessage"] if "errorMessage" in config else
    f'{config["recordName"].capitalize()} "{recordValue}" already exists')


def MergeConfigs(config, defaultConfig):
    return defaultConfig if config is None else {**defaultConfig, **config} if type(config) is dict else config

def CheckPatchRelationshipCollection(patchReq, collectionName, configArg=None):
    config = MergeConfigs(configArg, {
        "collectionOperations": ["add", "remove"],
        "collectionItems": {
            "type": int,
            "typeStr": "int",
        },
        "collectionItemsName": "item",
       "deleteCollection": False
    })

    result = {
        "collectionFound": False,
        "validatedCollection": {},
    }
    if collectionName in patchReq:
        if type(patchReq[collectionName]) is dict:
            for operation in config["collectionOperations"]:
                if operation in patchReq[collectionName]:
                    if type(patchReq[collectionName][operation]) is list:
                        for entryId in patchReq[collectionName][operation]:
                            if not type(entryId) is config["collectionItems"]["type"]:
                                return False, {
                                    "retMsg": f"{config['collectionItemsName'].capitalize()} id '{entryId}' from "
                                              f"'{operation}' operation must be {config['collectionItems']['typeStr']}",
                                    "httpStatus": 400
                                }
                        operationCollection = frozenset(patchReq[collectionName][operation])
                        if len(operationCollection) > 0:
                            result["validatedCollection"][operation] = operationCollection
            result["collectionFound"] = True
        if config["deleteCollection"]:
            del(patchReq[collectionName])
    return True, result

def DoPatchRelationshipOperations(patchOperations, dbSession, relationshipModel, column, relatedColumn, itemId,
                                  relationShipModelBuilder):
    if "remove" in patchOperations:
        from sqlalchemy import and_
        relationshipModel.query.filter(and_(
            relatedColumn.in_(patchOperations["remove"]),
            column == itemId
        )).delete(synchronize_session=False)

    if "add" in patchOperations:
        for operationItemId in patchOperations["add"]:
            dbSession.add(relationShipModelBuilder(operationItemId))
    dbSession.commit()

g_permittedOsList = ("linux", "win", "macos", "android", "ios")
