import os
from flask_restx import Api
from flask_restx.fields import MarshallingError
import settings
from Utils.SettingsUtils import EnvOrSetting, EnvOrValue

def DocUrl():
    """
        Retrieves the doc setting as needed by the flask_restx Api class doc param based on two settings:
            * swagger documentation switch:  DOC environment variable if defined or settings.SWAGGER_DOC
                and
            * swagger documentation url prefix: DOC_PREFIX environment variables if defined or settings.SWAGGER_DOC_URL

    :return: the doc setting as needed by the flask_restx Api class. If False then the documentation is disabled
    """
    def DocPrefixUrl():
        return EnvOrSetting("DOC_PREFIX", "SWAGGER_DOC_PREFIX")

    if "DOC" in os.environ:
        return DocPrefixUrl() if os.environ["DOC"].lower() in ("on", "1", "true") else False
    else:
        return DocPrefixUrl() if settings.SWAGGER_DOC else False

#the app object will attach the api object, in its constructor
#ToDo: implement an Api adapter so that route method prints info about endpoints, on Debug (see settings.FLASK_DEBUG)
g_theApi = Api(title="Management rest api", description="Rest api for privately managing sensitive info like "
                                                        "organizations, users and servers PKI infrastructures",
               doc=DocUrl(),
               prefix = EnvOrSetting("DOC_PRFIX"),
               default_label = "Management namespace", default="Management",
               version=f'1.0{EnvOrValue("VERSION_EXTRA", "")}')


@g_theApi.errorhandler(MarshallingError)
def MarshalingErrorHandler(e):
    """
        Marshaling error handler for returnig the error as json resopnse to the http client

    :param e: the original exception which trigger the handler error
    :return: a tuple composed by the json message and http status code
    """
    eStr = str(e).replace('"', "'")
    return {"message": f"{eStr}"}, 500

from marshmallow import Schema, fields

class EntityLikeSchemaBase(Schema):
    """
        Base class for all entity like clases, such as Orgs, Users and Servers
    """
    _entityName = ""
    name = fields.String(required = True,
                         description = _entityName.capitalize() + ' name')
    country = fields.String(required=True,
                            description=_entityName.capitalize() + ' country')
    state = fields.String(required=True,
                          description=_entityName.capitalize() + ' state')
    location = fields.String(required=True,
                             description=_entityName.capitalize() + ' location')
    email = fields.Email(required=True,
                         description=_entityName.capitalize() + ' email')
