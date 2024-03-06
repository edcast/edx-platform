import hashlib
from .credentials import cm_credentials

import logging

log = logging.getLogger(__name__)

# edcustom: Validate token function to check if the given token matches the expected token
def validate_token(string_to_validate, request):
    # edcustom: Retrieve X-Savannah-Token from request headers
    x_savannah_token = request.headers.get('HTTP_X_SAVANNAH_TOKEN') or request.META.get('HTTP_X_SAVANNAH_TOKEN')
    if x_savannah_token is not None:
        return validate_x_savannah_token(string_to_validate, x_savannah_token)
    else:
        return False

# edcustom: Validate X-Savannah-Token function to check if the generated token matches the given token
def validate_x_savannah_token(body, x_savannah_token):
    shared_secret = cm_credentials('shared_secret').rstrip() # edcustom: Retrieve shared secret from credentials
    hash_data = f"{shared_secret}|{body.decode('utf-8')}"
    token = hashlib.sha256(hash_data.encode('utf-8'))
    log.info(f"Token : {token.hexdigest()}")
    return token.hexdigest() == x_savannah_token  # edcustom: Compare the generated token with the given token