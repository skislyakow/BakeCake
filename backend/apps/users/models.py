from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, phone, name="", email="", password=None, **extra):
        if not phone:
            raise ValueError("Номер телефона обязателен")
        user = self.model(phone=phone, name=name, email=self.normalize_email(email), **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, phone, name="", email="", **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(phone, name, email, **extra)

    def create_superuser(self, phone, name="", email="", **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError("У суперпользователя must be is_staff=True and is_superuser=True")
        return self._create_user(phone, name, email, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    phone = models.CharField("телефон", max_length=20, unique=True)
    name = models.CharField("имя", max_length=100, blank=True)
    email = models.EmailField("почта", blank=True)
    is_staff = models.BooleanField("сотрудник", default=False)
    is_active = models.BooleanField("активен", default=True)
    date_joined = models.DateTimeField("регистрация", default=timezone.now)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = ["name"]

    objects = UserManager()

    class Meta:
        verbose_name = "пользователь"
        verbose_name_plural = "пользователи"
        ordering = ["-date_joined"]

    def __str__(self):
        return f"{self.name or 'Без имени'} ({self.phone})"


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    default_address = models.CharField("адрес по умолчанию", max_length=300, blank=True)
    consent_pdp_at = models.DateTimeField("согласие на ПД", null=True, blank=True)
    consent_pdp_ip = models.GenericIPAddressField("IP согласия", null=True, blank=True)
    pd_version = models.CharField("версия согласия", max_length=20, blank=True)

    class Meta:
        verbose_name = "профиль"
        verbose_name_plural = "профили"

    def __str__(self):
        return f"Профиль {self.user.phone}"
