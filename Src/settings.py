import os

# Flask settings
FLASK_DEBUG = False  # Do not use debug mode in production or when debugging with a debugger
FLASK_RELOADER = False
# FLASK_HOST = os.getenv("HOST", "localhost")
# FLASK_PORT = os.getenv("PORT", "8083")
# FLASK_SERVER_NAME = f'{FLASK_HOST}:{FLASK_PORT}'
FLASK_ALLOWED_ORIGINS = ["https://www.liny.io"]
FLASK_CERTS_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "Certs") #relative to the current script path

FLASK_TMP_BASE = "/tmp/LinyTmp"
FLASK_CLEAN_TMP_BASE_AT_STARTUP = False #must not be active in production, with multiple threads. It will erase the other valid tmp dirs

# SQLAlchemy settings
SQLALCHEMY_DATABASE_URI = 'sqlite:///../db.sqlite'
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ECHO = False
SQLALCHEMY_CHECK_SAME_THREAD = False
SQLALCHEMY_RECORD_QUERIES = True

#Swagger settings
#determine if the swagger api documentation will be enabled
SWAGGER_DOC = False

#the swagger api documentation url if enabled
SWAGGER_DOC_PREFIX= "/apidocs/"

REST_SWAGGER_UI_DOC_EXPANSION = 'list'
REST_VALIDATE = True
REST_MASK_SWAGGER = False
REST_ERROR_404_HELP = False

#Web management service rest api
DOC_PRFIX = "/api/v1"

#limits
LIMIT_ORGS = 1000 #maximum number of organizations
LIMITS_ENTITIES = 100000 #maximum number of entities

OVPN_PATH="/usr/sbin/openvpn"

#Todo: allow enabling granular api endpoints. For now all endpoints will be enabled
# ORGS = True
# USERS = True #implies ORGS = True
# SERVERS = True #implies ORGS = True
# CERTS = True #implies ORGS, USERS and SERVERS = True
