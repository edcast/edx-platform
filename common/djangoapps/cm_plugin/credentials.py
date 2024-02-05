from yaml import load
from yaml import YAMLObject, Loader, Dumper
import logging
import re
from django.conf import settings

log = logging.getLogger(__name__)


def _app_id():
    return settings.EDCAST_APP_ID

def _lms_id():
    return settings.EDCAST_LMS_ID

def _callback_url():
    return settings.EDCAST_CALLBACK_URL

def _environment():
    return settings.EDCAST_ENVIRONMENT

def _api_key():
    return settings.EDCAST_API_KEY

def _shared_secret():
    return settings.EDCAST_SHARED_SECRET

# permitted lookup values for the YAML file. These need to be updated
# along with any update in the YAML file.

KEYS = {
    'app_id': _app_id,
    'lms_id': _lms_id,
    'api_key': _api_key,
    'callback_url': _callback_url,
    'shared_secret': _shared_secret,
    'environment': _environment
}


# Sole function exposed as the API from this module.
# allows lookup in the metadata file based on the incoming request.
# raises KeyError and fails silently by returning none for any
# illegal request.

# each call results in an IO. For multiple usage of cm_credentials(key), 
# it is preferred to assigns the value to a variable and use the variable
# as needed.
def cm_credentials(key):
    try:
        return KEYS[key]()
    except KeyError:
        return None
