from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

from .utils import normalize_phone


class PhoneBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        return super().authenticate(request, username=normalize_phone(username), password=password, **kwargs)