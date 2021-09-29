class ConfigTemplateInfoEntry:
    m_info = None

    def __init__(self, moduleName: str, configArg=None):
        if configArg is None:
            configArg = {}

        self.m_config = {
            **configArg,
            "moduleName": configArg["packageName"] + "." + moduleName if "packageName" in configArg else
                "Api.OvpnConfigTemplates." + moduleName,
            "default": configArg["default"] if "default" in configArg else False
        }
        #
        # self.m_module = moduleName
        # self.m_package = package

    def __getitem__(self, key):
        if key in self.m_config:
            return self.m_config[key]
        #
        # if key == "path" :
        #     return self.m_config[m_moduleName]
        elif key == "module":
            module = __import__(self.m_config["moduleName"], globals(), locals(), ["ConfigTemplate"])
            self.m_config["module"] = module
            return module
        elif key == "classObj":
            classObj = self["module"].ConfigTemplate
            self.m_config["classObj"] = classObj
            return classObj
        else:
            if self.m_info is None:
                # self.m_info = __import__(self.m_package + "." + self.m_module, globals(), locals(), ["ConfigTemplate"]).\
                # self.m_info = __import__(self.m_config["moduleName"], globals(), locals(), ["ConfigTemplate"]).\
                #     ConfigTemplate.Info()
                self.m_info = self["classObj"].Info()
            return self.m_info[key]


from flask_restx import abort


def ConfigVarsFromReqArgs(reqArgs):
    from Utils.Misc import g_permittedOsList

    osParam = reqArgs.get("os", "linux")
    if osParam not in g_permittedOsList:
        abort(400, f"Invalid os. It must be in {g_permittedOsList} list")
    return {
        "os": osParam,
        "srvHost": reqArgs.get("srvHost", "localhost"),
    }


def ClientConfigVarsFromReqArgs(reqArgs):
    ports = reqArgs.getlist("port[]", int)
    protos = reqArgs.getlist("proto[]")
    if len(ports) != len(protos):
        abort(400, "Unmatched number of ports and protocols")
    elif len(ports) == 0:
        ports.append("1194")
        protos.append("udp")
    elif len(ports) > 2:
        ports = ports[0 : 2]
        protos = protos[0 : 2]
    if protos[0] == protos[1] and ports[0] == ports[1]:
        protos.pop()
        ports.pop()

    return {
        **ConfigVarsFromReqArgs(reqArgs),
        "ports": ports,
        "protos": protos
    }

def SrvConfigVarsFromReqArgs(reqArgs):
    baseConfigVars = ClientConfigVarsFromReqArgs(reqArgs)

    from ipaddress import IPv4Network, IPv4Address
    defaultNets = [ IPv4Network("10.113.0.0/24"), IPv4Network("10.113.1.0/24") ][:len(baseConfigVars["ports"])]
    try:
        nets = reqArgs.getlist("net[]", type = IPv4Network)
        if len(nets) == 0:
            nets = defaultNets[:len(baseConfigVars["ports"])]
        elif  len(nets) > len(baseConfigVars["ports"]):
            nets = nets[:len(baseConfigVars["ports"])]
        elif len(nets) == len(baseConfigVars["ports"]) - 1: #ie nets has one element and port two elements
            nets.append(IPv4Network(str(IPv4Address(int(nets[0].network_address) + (1<< (32 - nets[0].prefixlen)))) + \
                    f"/{nets[0].prefixlen}"))
        assert(len(nets) == len(baseConfigVars["ports"]))
        # else: #should never happen
        #     nets = defaultNets
    except:
        nets = defaultNets
    return {
        **baseConfigVars,
        "nets": nets
        # **{key[0]: reqArgs.get(key[0], key[1], key[2]) for key in [
        #     ("ports", 1194, int),
        #     ("protos", "udb", str)
        # ]}
    }

def EntityTypeToConfigTemplateType(entityType):
    return "client" if entityType == "user" else entityType

    # def GetReqArg(req, argName, argType = str, defaultArgValue = None):
    #     reqArg = req.args.get(argName, defaultArgValue)
    #     return argType(reqArg) if type(reqArg) == str else None
    #
    # def GetReqArgList(req, argName, argListElemType = str):
    #     reqArgList = req.args.getlist
    #     return GetReqArg(req, argName, argListElemType)

def ConfigFromReqArgs(reqArgs, argsNames, initialConfig = None):
    resConfig = initialConfig if type(initialConfig) == dict else {}
    for argName in argsNames:
        if type(argName) == dict:
            name = argName["name"]
            argDefault = argName.get("default", None)
            argGetType = argName.get("type", type(argDefault) if argDefault is not None else str)
            postFunc = argName["post"] if "post" in argName and callable(argName["post"]) else None
            reqSearchNames = argName["reqSearchNames"] if "reqSearchNames" in argName else [name]
        else:
            name = argName
            argDefault = None
            argGetType = str
            postFunc = None
            reqSearchNames = [name]
        for reqSearchName in reqSearchNames:
            if reqSearchName in reqArgs:
                try:
                    reqArg = reqArgs.get(reqSearchName, default=argDefault, type=argGetType)
                    if callable(postFunc):
                        reqArg = postFunc(reqArg)
                    resConfig[name] = reqArg
                except:
                    pass
            elif argDefault is not None:
                resConfig[name] = argDefault
    return resConfig

def DateTimeFromStr(dateStr): #assumes valid date str, in the form YYYY-MM-DD
    from datetime import datetime
    dateComponents = dateStr.split(sep="-")
    if len(dateComponents) ==    1:
        dateComponents = dateStr.split(sep=".")
    return datetime(*[int(dateComponent) for dateComponent in dateComponents]) if len(dateComponents) >= 3 else dateStr

def ValidProtoStr(protoStr):
    return protoStr in ["tcp", "udp"]
