import typing

g_verMajor = 0
g_verMinor = 1

class ConfigTemplateBase:
    @staticmethod
    def Info(): #define it in derived classes
        return {
            "type": "genericType",
            "name": "Generic config template",
            "description": "Generic description",
            "version": f"{g_verMajor}.{g_verMinor}"
        }

    def __init__(self, configVars: typing.Dict):
        self.m_configVars = {
            "verMajor": g_verMajor,
            "verMinor": g_verMinor,
            ** configVars,
        }

    def Instantiate(self) -> typing.Tuple[typing.IO, str]:
        from Utils.Misc import g_permittedOsList as permittedOsList
        assert self.m_configVars["os"] in permittedOsList
        return self._DoInstantiate()

    def Name(self):
        return f'{self.BaseName()}.{self.Ext()}'

    def ArchName(self): #return the archive name if the case or None otherwise
        return None

    def BaseName(self):
        return "liny-ovpn"

    def Ext(self):
        return f'{"conf" if self.m_configVars["os"] == "linux" else "ovpn"}'

    def _DoInstantiate(self) -> typing.Tuple[typing.IO, str]: #must be defined by the sub-class
        pass

