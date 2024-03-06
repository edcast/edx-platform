import json
import time
from django.utils.http import http_date
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth import login, authenticate
from .credentials import cm_credentials
from .token import validate_token
from .aes import decrypt


# edcustom: Middleware for handling external authentication
class ExternalAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.process_request(request) # edcustom: Process the request
        response = self.get_response(request)
        response = self.process_response(request, response)
        return response

    # Process the request
    def process_request(self, request):
        # edcustom: Check if token is passed in the request
        if self.is_token_passed(request):
            # edcustom: Get normalized user data
            user_data = self.get_normalized_user_data(request)
            # edcustom: Check if user is authenticated and update if necessary
            if request.user is not None and request.user.is_authenticated:
                # edcustom : If user is authenticated, compare user data with request data and update if necessary
                if (request.user.email != user_data['email']) or \
                        (user_data['username'] != '' and request.user.username != user_data['username']):
                    # edcustom: Authenticate and update user
                    self.auth_user(request, user_data)
            else:
                # edcustom: If user is not authenticated, authenticate user
                self.auth_user(request, user_data)

    def process_response(self, request, response):

        # edcustom: Skip the entire shebang if token is not passed
        if not self.is_token_passed(request):
            return response

        # 1. If request.user is present
        if request.user is not None:
            # 2. If request.user is authenticated, just return response
            if request.user.is_authenticated:
                return response

            # 3. If request.user is not authenticated, try authenticating the user
            user_data = self.get_normalized_user_data(request)
            self.auth_user(request, user_data)

            # 4. Set session expiry
            request.session.set_expiry(604800)

        # 5. Set cookie
        max_age = 1209600
        expires_time = time.time() + max_age
        expires = http_date(expires_time)

        response.set_cookie(settings.EDXMKTG_LOGGED_IN_COOKIE_NAME,
                            'true', max_age=max_age,
                            expires=expires, domain=settings.SESSION_COOKIE_DOMAIN,
                            path='/',
                            secure=None,
                            httponly=None)

        return response

    # edcustom: Get the encrypted GET param named 'token', else return a blank string
    def get_token(self, request):
        token = request.GET.get('token', '')
        if request.headers.get('HTTP_X_USER_TOKEN') and validate_token(request.body, request):
            token = request.headers.get('HTTP_X_USER_TOKEN', '')

        return token

    # edcustom: Get the decrypted GET param named 'token', else return a blank string
    def get_email(self, request):
        key = cm_credentials('shared_secret')[:16]
        encrypted_token = self.get_token(request)

        return decrypt(encrypted_token, key, '\x01') if encrypted_token else ''

    # edcustom: Get the encrypted GET param named 'ext_token', else return '{}'
    def get_ext_token(self, request):
        # edcustom: Get the ext token from either GET parameters or request headers
        token = request.GET.get('ext_token', '') # edcustom: Get ext token from GET parameters
        if request.headers.get('HTTP_X_USER_EXT_TOKEN') and validate_token(request.body, request):
            # edcustom: If X_USER_EXT_TOKEN exists in headers and token validation is successful,
            # get the token from headers
            token = request.headers.get('HTTP_X_USER_EXT_TOKEN', '')

        return token

    # Get the decrypted GET param named 'ext_token', and return a data structure
    # {
    #   email: ''
    #   username: ''
    # }
    # This function will never return an error, and in the absence of good data, will return
    # blank for both email and username

    def get_user_data(self, request):
        # Get the key for decryption
        key = cm_credentials('shared_secret')[:16]
        # edcustom: Get the encrypted token from the request
        encrypted_token = self.get_ext_token(request)
        # edcustom: Decrypt the token using the key, if token exists, otherwise set token to '{}'
        token = decrypt(encrypted_token, key, '\x0e') if encrypted_token else '{}'
        try:
            # Parse the decrypted token
            parsed_token = json.loads(token)
        except json.JSONDecodeError:
            # If parsing fails, set parsed_token to an empty dictionary
            parsed_token = {}
        # edcustom: Extract email and username from the parsed token, defaulting to empty strings
        email = parsed_token.get('email', '')
        username = parsed_token.get('username', '')
        # Return a dictionary containing email and username
        return {'email': email, 'username': username}


    # Get both email from the token, and the user data from ext_token.
    # Normalize both of them into a data consistent data structure
    # {
    #   email: ''
    #   username: ''
    # }
    # edcustom: Get normalized user data from request
    def get_normalized_user_data(self, request):
        # Get email from token if present, otherwise from ext token
        token_email = self.get_email(request)
        ext_user_data = self.get_user_data(request)
        email = token_email if token_email else ext_user_data.get('email', '')

        # If email is not available, raise an exception
        if not email:
            raise InvalidAuthDetails('Email was not passed')
        # Check for consistency between token email and ext token email
        if token_email and ext_user_data['email'] and token_email != ext_user_data['email']:
            raise InvalidAuthDetails('Inconsistent email passed in token and ext_token')
        # Return normalized user data
        return {'email': email, 'username': ext_user_data.get('username', '')}

    # edcustom: Check if both token and ext token are passed in the request
    def is_token_passed(self, request):
        return bool(self.get_token(request) and self.get_ext_token(request))

    # edcustom: Get user object from user data
    def get_user_from_user_data(self, user_data):
        try:
            # Get user by username if available, otherwise by email
            if user_data['username']:
                user = User.objects.get(username=user_data['username'])
            else:
                user = User.objects.get(email=user_data['email'])
        except User.DoesNotExist:
            user = None
        return user

    # edcustom: Authenticate user and perform login
    def auth_user(self, request, user_data):
        user = self.get_user_from_user_data(user_data)
        # edcustom: If user exists and is active, authenticate and login
        if user and user.is_active:
            try:
                # auth_params = {'username': user_data['username'], 'email': user_data['email']}
                # user = authenticate(**auth_params)
                login(request, user, backend='common.djangoapps.cm_plugin.backends.EmailAuthBackend')
                request.user = user
            except Exception as e:
                raise  # edcustom: Handle exception, probably memcache is down


# edcustom: Custom exception for invalid authentication details
class InvalidAuthDetails(ValueError):
    pass
