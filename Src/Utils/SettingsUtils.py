import settings #as settingsFile
import os

LIST_SPLIT_CHAR = ','

def EnvOrSetting(envName, settingName = None, defaultValue = None):
    """
        Retrieves the environment variable if set or setting from the settings.py file otherwise
    :param envName: the environment variable
    :param settingName: the setting string defined in the settings.py file
    :return: the env variable if set or setting from the settings.py file otherwise
    """
    if settingName is None:
        settingName = envName
    try:
        return EnvOrValue(envName, getattr(settings, settingName))
    except AttributeError:
        return EnvOrValue(envName, defaultValue)

def EnvOrValue(envName, value = ""):
    # return os.environ[envName] if envName in os.environ else value
    res = os.getenv(envName, value)
    if type(res) == str:
        if type(value) == bool:
            res = res.lower()
            return True if res in [ "1", "on", "true"] else False if res in [ "0", "off", "false"] else value
        elif type(value) == list:
                return [s.strip() for s in res.split(LIST_SPLIT_CHAR)]
    return res