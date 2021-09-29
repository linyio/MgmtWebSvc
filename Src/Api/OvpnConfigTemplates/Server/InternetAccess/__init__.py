# import typing
from Api.OvpnConfigTemplates.Common.ConfigTemplateBase import ConfigTemplateBase
from io import BytesIO

from Api.OvpnConfigTemplates.Utils import ValidProtoStr
from Utils import CertsUtils

#available only on Linux - x64
from Utils.CertsUtils import KeysOpener

class ConfigTemplate(ConfigTemplateBase):
    @staticmethod
    def Info():
        return {
            "version": super(ConfigTemplate, ConfigTemplate).Info()["version"],
            "type": "server",
            "name": "Internet access (srv)",
            "description": "Simple OpenVPN server configuration for provinding DNS and internet access",
        }

    def BaseName(self):
        return super().BaseName() + "-srv-conf"

    def ArchName(self):
        return self.BaseName() + ".tar.xz"

    def _DoInstantiate(self):
        def InstantiateConfs():
            # self.m_configVars["protosOrig"] = self.m_configVars["protos"]
            # self.m_configVars["portsOrig"] = self.m_configVars["ports"]
            for (idx, proto) in enumerate(self.m_configVars["protos"]):
                self.m_configVars["netAddress"] = str(self.m_configVars["nets"][idx].network_address)
                self.m_configVars["netMask"] = str(self.m_configVars["nets"][idx].netmask)
                from ipaddress import IPv4Address, IPv4Network
                self.m_configVars["srvIp"] = str(IPv4Address(int(self.m_configVars["nets"][idx].network_address) + 1))
                if len(self.m_configVars["nets"]) > 1:
                    pushRouteDirectives = "#push the route (to the client) for reaching clients connected through the " \
                                          "other OpenVPN connection\n"
                    for netIdx, net in enumerate(self.m_configVars["nets"]):
                        if netIdx != idx:
                            pushRouteDirectives += f"push \"route {str(net.network_address)} {str(net.netmask)}\"\n"
                    self.m_configVars["pushRouteDirectives"] = pushRouteDirectives + "\n"
                else:
                    self.m_configVars["pushRouteDirectives"] = ""

                InstantiateOvpnConf(proto, self.m_configVars['ports'][idx])

            del self.m_configVars["netAddress"]
            del self.m_configVars["netMask"]
            del self.m_configVars["pushRouteDirectives"]
            del self.m_configVars["srvIp"]

        def InstantiateOvpnConf(protoStr, port):
            if not ValidProtoStr(protoStr):
                from flask_restx import abort
                abort(400, "Invalid proto - " + protoStr)
            self.m_configVars["proto"] = protoStr
            self.m_configVars["port"] = port
            confTemplate = ""
            with open(os.path.join(os.path.dirname(__file__), "Confs", "Openvpn", f"server-{protoStr}.conf"), 'r') as f:
                from string import Template
                confTemplate = Template(f.read(100000)) #max 100000 chars to read
            with open(os.path.join(ovpnTmpConfsDir, f"server-{protoStr}-{port}.conf"), "wt", newline='\n') as f:
                confStr = confTemplate.safe_substitute(self.m_configVars)
                f.write(confStr)

                try:
                    import re
                    ccd = re.search("^\s*client-config-dir\s*(\S*)", confStr, re.MULTILINE).group(1)
                    if len(ccd):
                        os.mkdir(os.path.join(ovpnTmpConfsDir, ccd), mode=0o755)
                except:
                    pass


        import os
        import tempfile

        with tempfile.TemporaryDirectory(None, "OvpnServerConfig-", self.m_configVars["tmpDir"]) as tmpConfsDir:
            ovpnTmpConfsDir = os.path.join(tmpConfsDir, "openvpn")
            import shutil
            os.mkdir(ovpnTmpConfsDir, mode=0o755)
            #copy dnsmasq.conf file
            shutil.copy(os.path.join(os.path.dirname(__file__), "Confs", "dnsmasq.conf"), tmpConfsDir)
            #copy the server template skeleton tree to tmp dir
            # shutil.copytree(os.path.join(os.path.dirname(__file__), 'Confs'), tmpConfsDir)
            InstantiateConfs()

            #copy to tmp dir the CA cert
            certsPath = os.path.join(ovpnTmpConfsDir, "server")
            os.mkdir(certsPath, mode=0o755) #create the certs subdir
            with open(os.path.join(certsPath, "LinyOvpnCA.crt"),
                      "wb") as f:
                f.write(self.m_configVars["caCert"])

            #copy to tmp dir the server's cert and key
            with open(os.path.join(certsPath, "LinyOvpn.crt"), "wb") as f:
                f.write(self.m_configVars["cert"])

            with open(os.path.join(certsPath, "LinyOvpn.key"), "wb",
                      opener=KeysOpener) as f:
                f.write(self.m_configVars["key"])

            #copy to tmp dir the server's specific files (such as tc.key
            with open(os.path.join(certsPath, "tc.key"), "wb", opener=KeysOpener) \
                    as f:
                f.write(self.m_configVars["tlsKey"])

            #copy to tmp dir the crl file
            with open(os.path.join(certsPath, "crl.pem"), "wb") as f:
                f.write(self.m_configVars["crl"])

            return CertsUtils.PackConfigTree(tmpConfsDir), self.ArchName()
