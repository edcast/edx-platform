from .credentials import cm_credentials
import hashlib

import logging

log = logging.getLogger(__name__)

def validate_token(string_to_validate, request):
    x_savannah_token = request.META.get('HTTP_X_SAVANNAH_TOKEN')
    if x_savannah_token is not None:
        return validate_x_savannah_token(string_to_validate, x_savannah_token)
    else:
        return False

def validate_x_savannah_token(body, x_savannah_token):
    shared_secret = cm_credentials('shared_secret').rstrip()
    hash_data = f"{shared_secret}|{body.decode('utf-8')}"
    token = hashlib.sha256(hash_data.encode('utf-8'))
    return token.hexdigest() == x_savannah_token