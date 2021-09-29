from flask_restx import Resource
from Api import g_theApi
from Utils.ResourcesUtils import JWTAuthResource


@g_theApi.route("/ovpnConfigNames/entityId/<int:entityId>",
                doc={"description": "retrieves the configuration name for givn entity (OpenVPN user or server)"})
class ConfigTemplatesNames(JWTAuthResource):
    def get(self, entityId):
        from Utils.ResourcesUtils import GetEntity
        from flask import request as req
        from Api.OvpnConfigTemplates import GetConfigTemplatesClass
        from Api.OvpnConfigTemplates.Utils import EntityTypeToConfigTemplateType, ConfigVarsFromReqArgs

        entity, entityType = GetEntity(entityId)
        configTemplateClass = GetConfigTemplatesClass(req.args.get("configTemplateId", None, int),
                                                          EntityTypeToConfigTemplateType(entityType))
        if configTemplateClass is not None:
            configTemplateClassInst = configTemplateClass({
                **ConfigVarsFromReqArgs(req.args),
                "entityName": entity.name
            })
            archName = configTemplateClassInst.ArchName()
            return {
                "confName": configTemplateClassInst.Name(),
                "confBaseName": configTemplateClassInst.BaseName(),
                "confExt": configTemplateClassInst.Ext(),
                **({
                    "archName": archName
                } if archName is not None else {})
            }, 200
        else:
            return "No config template could be located for the provided entity type", 500
