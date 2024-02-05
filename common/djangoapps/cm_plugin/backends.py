from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User


class EmailAuthBackend(ModelBackend):
    """Log in to Django without providing a password.
    """
    def authenticate(self, email=None, username=None):
        try:
            if username is not None and username != '':
                return User.objects.get(username=username)
            else:
                return User.objects.get(email=email)
        except User.DoesNotExist:
            return None
