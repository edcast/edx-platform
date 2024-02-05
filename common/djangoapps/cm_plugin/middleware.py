import json
import time
from django.utils.http import http_date
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth import login, authenticate
from .credentials import cm_credentials
from .token import validate_token
from .aes import decrypt


class ExternalAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.process_request(request)
        response = self.get_response(request)
        response = self.process_response(request, response)
        return response

    def process_request(self, request):
        if self.is_token_passed(request):
            user_data = self.get_normalized_user_data(request)
            if request.user is not None and request.user.is_authenticated:
                if (request.user.email != user_data['email']) or \
                        (user_data['username'] != '' and request.user.username != user_data['username']):
                    self.auth_user(request, user_data)
            else:
                self.auth_user(request, user_data)

    def process_response(self, request, response):
        if not self.is_token_passed(request):
            return response

        if request.user is not None:
            if request.user.is_authenticated:
                return response

            user_data = self.get_normalized_user_data(request)
            self.auth_user(request, user_data)
            request.session.set_expiry(604800)

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

    def get_token(self, request):
        token = request.GET.get('token', '')
        if request.headers.get('HTTP_X_USER_TOKEN') and validate_token(request.body, request):
            token = request.headers.get('HTTP_X_USER_TOKEN', '')
        return token

    def get_email(self, request):
        key = cm_credentials('shared_secret')[:16]
        encrypted_token = self.get_token(request)
        return decrypt(encrypted_token, key, '\x01') if encrypted_token else ''

    def get_ext_token(self, request):
        token = request.GET.get('ext_token', '')
        if request.headers.get('HTTP_X_USER_EXT_TOKEN') and validate_token(request.body, request):
            token = request.headers.get('HTTP_X_USER_EXT_TOKEN', '')
        return token

    def get_user_data(self, request):
        key = cm_credentials('shared_secret')[:16]
        encrypted_token = self.get_ext_token(request)
        token = decrypt(encrypted_token, key, '\x0e') if encrypted_token else '{}'
        try:
            parsed_token = json.loads(token)
        except json.JSONDecodeError:
            parsed_token = {}
        email = parsed_token.get('email', '')
        username = parsed_token.get('username', '')
        return {'email': email, 'username': username}

    def get_normalized_user_data(self, request):
        token_email = self.get_email(request)
        ext_user_data = self.get_user_data(request)
        email = token_email if token_email else ext_user_data.get('email', '')
        if not email:
            raise InvalidAuthDetails('Email was not passed')
        if token_email and ext_user_data['email'] and token_email != ext_user_data['email']:
            raise InvalidAuthDetails('Inconsistent email passed in token and ext_token')
        return {'email': email, 'username': ext_user_data.get('username', '')}

    def is_token_passed(self, request):
        return bool(self.get_token(request) and self.get_ext_token(request))

    def get_user_from_user_data(self, user_data):
        try:
            if user_data['username']:
                user = User.objects.get(username=user_data['username'])
            else:
                user = User.objects.get(email=user_data['email'])
        except User.DoesNotExist:
            user = None
        return user

    def auth_user(self, request, user_data):
        user = self.get_user_from_user_data(user_data)
        if user and user.is_active:
            try:
                # auth_params = {'username': user_data['username'], 'email': user_data['email']}
                # user = authenticate(**auth_params)
                login(request, user, backend='common.djangoapps.cm_plugin.backends.EmailAuthBackend')
                request.user = user
            except Exception as e:
                raise  # probably memcache is down

class InvalidAuthDetails(ValueError):
    pass
