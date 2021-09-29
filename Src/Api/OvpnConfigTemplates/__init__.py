# from Api.OvpnConfigTemplates import ConfigTemplateInfoEntry
from Api.OvpnConfigTemplates.Utils import ConfigTemplateInfoEntry

g_ovpnConfigTemplates = [
        ConfigTemplateInfoEntry("Server.InternetAccess", {
            "id": 1,
            "default": True #only one server template must be default. The others shouldn't include it at all
        }),
        ConfigTemplateInfoEntry("Client.InternetAccess", {
            "id": 2,
            "default": True #only one client template must be default. The others shouldn't include it at all
        })
]

def GetConfigTemplatesClass(configTemplateId : int, configTemplateType: str):
    global g_ovpnConfigTemplates
    resClassObj = None
    if configTemplateId is None: #auto-determine default or first config template of type configTemplateType
        candidateTemplate = None
        for idx, configTemplateEntry in enumerate(g_ovpnConfigTemplates):
            if configTemplateEntry["type"] == configTemplateType:
                candidateTemplate = configTemplateEntry
                # if configTemplateId is None:
                #     configTemplateId = idx + 1
                if configTemplateEntry["default"]:
                    # configTemplateId = idx + 1
                    # break #the first default entry was found. Just exit the for
                    return configTemplateEntry["classObj"]
        return candidateTemplate
    else:
        return g_ovpnConfigTemplates[configTemplateId - 1]["classObj"] if \
            0 < configTemplateId <= len(g_ovpnConfigTemplates) and \
            g_ovpnConfigTemplates[configTemplateId - 1]["type"] == configTemplateType else None
