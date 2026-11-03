from django.contrib.auth.backends import ModelBackend

from .models import User
from .utils import normalize_phone


class PhoneBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        return super().authenticate(request, username=normalize_phone(username), password=password, **kwargs)
