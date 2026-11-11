from typing import Any

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import Profile, User
from .utils import normalize_phone


class _NormalizePhoneFormMixin:
    """Админка проверяет уникальность до `save()`, поэтому номер приводим здесь:
    иначе дубль в другом формате пройдёт валидацию и упадёт на unique-индексе.
    """

    cleaned_data: dict[str, Any]

    def clean_phone(self):
        return normalize_phone(self.cleaned_data.get("phone"))


class PhoneNormalizedUserChangeForm(_NormalizePhoneFormMixin, UserChangeForm):
    pass


class PhoneNormalizedUserCreationForm(_NormalizePhoneFormMixin, UserCreationForm):
    pass


@admin.register(User)
class BakeCakeUserAdmin(UserAdmin):
    form = PhoneNormalizedUserChangeForm
    add_form = PhoneNormalizedUserCreationForm
    list_display = ("phone", "name", "is_staff", "date_joined")
    list_filter = ("is_staff", "is_active", "date_joined")
    search_fields = ("phone", "name", "email")
    ordering = ("-date_joined",)
    fieldsets = (
        (None, {"fields": ("phone", "name", "email")}),
        ("Права", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Даты", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("phone", "name", "is_staff", "is_superuser")}),
    )
    readonly_fields = ("password",)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "default_address", "consent_pdp_at", "pd_version")
    list_filter = ("pd_version",)
    search_fields = ("user__phone", "user__name", "default_address")
    raw_id_fields = ("user",)
