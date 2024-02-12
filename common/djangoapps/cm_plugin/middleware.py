from django.http import HttpResponse
import json
import time
from django.utils.http import cookie_date
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth import login, authenticate
import aes
from credentials import cm_credentials
from cm_plugin.token import validate_token
import urllib
import json

# ugly.
# this is the mother of all insecure authentication systems.
# TODO: share secret key between edx and cm and send token values
# with AES encryption.
class ExternalAuthMiddleware(object):
    def process_request(self, request):
        # ugly hack 1
        # authenticate user based on email. This will be a non persistent authentication
        # required to bypass djangos @login_required decorator. no session or cookie can
        # be set here.

        # 1. Act only if token or ext_token has been provided
        if self.is_token_passed(request):
            user_data = self.get_normalized_user_data(request)

            # 2. If request.user is already present and authenticated, check if its email matches the token
            if request.user is not None and request.user.is_authenticated():
                # 3. If mismatch, re-auth user
                if (request.user.email != user_data['email']) or \
                        (user_data['username'] != '' and request.user.username != user_data['username']):
                    self.auth_user(request, user_data)

            # 4. If request.user is absent, then auth user
            else:
                self.auth_user(request, user_data)


    def process_response(self, request, response):
        # ugly hack 2
        # this takes the response from the logged in view, authenticates the user again based on token,
        # adds user session to memcache and sends a cookie back to browser.
        # This makes sure that the entire auth process is successful.

        # Skip the entire shebang if token is not passed
        if not self.is_token_passed(request):
            return response

        # 1. If request.user is present
        if request.user is not None:
            # 2. If request.user is authenticated, just return response
            if request.user.is_authenticated():
                return response

            # 3. If request.user is not authenticated, try authenticating the user
            user_data = self.get_normalized_user_data(request)
            self.auth_user(request, user_data)

            # 4. Set session expiry
            request.session.set_expiry(604800)

        # 5. Set cookie
        max_age = 1209600
        expires_time = time.time() + max_age
        expires = cookie_date(expires_time)

        response.set_cookie(settings.EDXMKTG_LOGGED_IN_COOKIE_NAME,
                            'true', max_age=max_age,
                            expires=expires, domain=settings.SESSION_COOKIE_DOMAIN,
                            path='/',
                            secure=None,
                            httponly=None)

        return response


    # Get the encrypted GET param named 'token', else return a blank string
    def get_token(self, request):
        token = request.GET.get('token', '')
        if request.META.get('HTTP_X_USER_TOKEN') and validate_token(request.body, request) == True:
            token = unicode(request.META.get('HTTP_X_USER_TOKEN',''))

        return token


    # Get the decrypted GET param named 'token', else return a blank string
    def get_email(self, request):
        key = cm_credentials('shared_secret')[0:16]
        encrypted_token = self.get_token(request)

        if encrypted_token == '':
            return ''
        else:
            return aes.decrypt(encrypted_token, key)


    # Get the encrypted GET param named 'ext_token', else return '{}'
    def get_ext_token(self, request):
        # Get the ext token verbatim
        token = request.GET.get('ext_token', '')
        if request.META.get('HTTP_X_USER_EXT_TOKEN') and validate_token(request.body, request) == True:
            token = unicode(request.META.get('HTTP_X_USER_EXT_TOKEN',''))

        return token


    # Get the decrypted GET param named 'ext_token', and return a data structure
    # {
    #   email: ''
    #   username: ''
    # }
    # This function will never return an error, and in the absence of good data, will return
    # blank for both email and username
    def get_user_data(self, request):
        key = cm_credentials('shared_secret')[0:16]
        encrypted_token = self.get_ext_token(request)

        if encrypted_token == '':
            token = '{}'
        else:
            token = aes.decrypt(encrypted_token, key)

        # Parse it
        parsed_token = {}
        try:
            parsed_token = json.loads(token)
        except json.JSONDecodeError:
            pass

        # Send back a normalized version
        email = ''
        if 'email' in parsed_token:
            email = parsed_token['email']

        username = ''
        if 'username' in parsed_token:
            username = parsed_token['username']

        return {
            'email': email,
            'username': username
        }


    # Get both email from the token, and the user data from ext_token.
    # Normalize both of them into a data consistent data structure
    # {
    #   email: ''
    #   username: ''
    # }
    def get_normalized_user_data(self, request):
        # Fetch data from token and ext_token
        token_email = self.get_email(request)
        ext_user_data = self.get_user_data(request)

        # Check if email data is present
        email = ''
        if token_email != '':
            email = token_email

        if ext_user_data['email'] != '':
            email = ext_user_data['email']

        if email == '':
            raise InvalidAuthDetails('Email was not passed')

        # Check if email in token and ext_user is consistent
        if token_email != '' and ext_user_data['email'] != '' \
            and token_email != ext_user_data['email']:

            raise InvalidAuthDetails('Inconsistent email passed in token and ext_token')

        return {
            'email': email,
            'username': ext_user_data['username']
        }


    # Returns a boolean on whether either of token or ext_token were passed
    def is_token_passed(self, request):
        token = self.get_token(request)
        ext_token = self.get_ext_token(request)

        if token == '' and ext_token == '':
            return False
        else:
            return True


    # Get a user from user_data, or return None if not found
    def get_user_from_user_data(self, user_data):
        try:
            if user_data['username'] != '':
                user = User.objects.get(username=user_data['username'])
            else:
                user = User.objects.get(email=user_data['email'])
        except User.DoesNotExist:
            user = None

        return user


    # Authenticate user based on the user_data passed
    def auth_user(self, request, user_data):
        user = self.get_user_from_user_data(user_data)

        if user is not None and user.is_active:
            try:
                auth_params = {'username': user_data['username'], 'email': user_data['email']}

                user = authenticate(**auth_params)
                login(request, user)
                request.user = user
            except Exception as e:
                raise # probably memcache is down


class InvalidAuthDetails(ValueError):
    pass
