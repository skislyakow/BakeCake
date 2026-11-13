import re

from django.db import migrations

_DIGITS_RE = re.compile(r"\D")


def normalize_phone(value):
    if not value:
        return ""
    raw = str(value).strip()
    digits = _DIGITS_RE.sub("", raw)
    if len(digits) == 10 and digits[:1] == "9":
        digits = "7" + digits
    if len(digits) == 11 and digits[:1] == "8":
        digits = "7" + digits[1:]
    if len(digits) == 11 and digits[:1] == "7":
        return "+" + digits
    return raw


def merge_duplicate_phones(apps, schema_editor):
    User = apps.get_model("users", "User")
    Order = apps.get_model("orders", "Order")
    Visit = apps.get_model("analytics", "Visit")
    Profile = apps.get_model("users", "Profile")

    groups = {}
    for user in User.objects.all():
        key = normalize_phone(user.phone)
        groups.setdefault(key, []).append(user)

    for key, users in groups.items():
        if not key or len(users) == 1:
            continue
        users.sort(key=lambda u: (u.phone != key, u.date_joined))
        keeper = users[0]
        for other in users[1:]:
            Order.objects.filter(user=other).update(user=keeper)
            Visit.objects.filter(user=other).update(user=keeper)
            try:
                loser_profile = other.profile
            except Profile.DoesNotExist:
                loser_profile = None
            if loser_profile is not None:
                Profile.objects.get_or_create(user=keeper)
                if not keeper.profile.default_address and loser_profile.default_address:
                    keeper.profile.default_address = loser_profile.default_address
                    keeper.profile.save()
                loser_profile.delete()
            other.delete()

    for user in User.objects.all():
        normalized = normalize_phone(user.phone)
        if normalized and user.phone != normalized:
            user.phone = normalized
            user.save(update_fields=["phone"])


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0001_initial"),
        ("orders", "0003_initial"),
        ("analytics", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(merge_duplicate_phones, migrations.RunPython.noop),
    ]
