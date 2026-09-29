import os
import sys
from datetime import date, time, timedelta
from pathlib import Path

import django
from django.conf import settings
from django.utils import timezone

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django.setup()

from apps.analytics.models import Visit
from apps.catalog.models import Cake
from apps.orders.models import Order
from apps.pricing.models import Option, OptionGroup
from apps.promo.models import PromoCode
from apps.users.models import Profile, User

OPTION_GROUPS = [
    {
        "code": "levels",
        "title": "Количество уровней",
        "is_required": True,
        "options": [("1 уровень", 400), ("2 уровня", 750), ("3 уровня", 1100)],
    },
    {
        "code": "form",
        "title": "Форма торта",
        "is_required": True,
        "options": [("Квадрат", 600), ("Круг", 400), ("Прямоугольник", 1000)],
    },
    {
        "code": "topping",
        "title": "Топпинг",
        "is_required": True,
        "options": [
            ("Без топпинга", 0),
            ("Белый соус", 200),
            ("Карамельный сироп", 180),
            ("Кленовый сироп", 200),
            ("Клубничный сироп", 300),
            ("Черничный сироп", 350),
            ("Молочный шоколад", 200),
        ],
    },
    {
        "code": "berries",
        "title": "Ягоды",
        "is_required": False,
        "options": [("Ежевика", 400), ("Малина", 300), ("Голубика", 450), ("Клубника", 500)],
    },
    {
        "code": "decor",
        "title": "Декор",
        "is_required": False,
        "options": [
            ("Фисташки", 300),
            ("Безе", 400),
            ("Фундук", 350),
            ("Пекан", 300),
            ("Маршмеллоу", 200),
            ("Марципан", 280),
        ],
    },
]
CAKES = [
    ("Чайный с лимоном", "chainyy-s-limonom", 2200, "img/image1.png", "На чаепитие", 0),
    ("Медовик", "medovik", 2600, "img/image1.png", "На чаепитие", 1),
    ("Пари брест", "pari-brest", 2400, "img/image1.png", "На чаепитие", 2),
    ("Шоколадный с вишней", "shokoladnyy-s-vishney", 2800, "img/image2.png", "На день рождения", 0),
    ("Наполеон", "napoleon", 3000, "img/image2.png", "На день рождения", 1),
    ("Морковный с грецким орехом", "morkovnyy-s-gretskim-orehom", 2700, "img/image2.png", "На день рождения", 2),
    ("Белая роза", "belaya-roza", 4200, "img/image3.png", "На свадьбу", 0),
    ("Три яруса с белым кремом", "tri-yarusa-s-belym-kremom", 5600, "img/image3.png", "На свадьбу", 1),
    ("Фруктовый", "fruktovyy", 3900, "img/image3.png", "На свадьбу", 2),
]
VISITS = [
    ("yandex", "cpc", "tor_2026", "/", "https://yandex.ru/"),
    ("yandex", "cpc", "tor_2026", "/", "https://yandex.ru/"),
    ("vk", "social", "animators", "/catalog/", "https://vk.com/"),
    ("instagram", "social", "stories", "/", "https://instagram.com/"),
    ("", "", "", "/", ""),
]
DEMO_CUSTOMER = {"phone": "89090000000", "name": "Ирина", "email": "i@mail.ru"}
DEMO_ADMIN = {"phone": "79990000000", "name": "Админ", "password": "BakeCake2026!"}


def seed_groups():
    for group_index, group in enumerate(OPTION_GROUPS, start=1):
        obj, _ = OptionGroup.objects.update_or_create(
            code=group["code"],
            defaults={"title": group["title"], "is_required": group["is_required"], "sort": group_index},
        )
        for option_index, (title, price) in enumerate(group["options"], start=1):
            Option.objects.update_or_create(
                group=obj, title=title, defaults={"price_delta": price, "sort": option_index}
            )
    print(f"групп опций: {OptionGroup.objects.count()}, опций: {Option.objects.count()}")


def seed_catalog():
    for name, slug, price, image, occasion, sort in CAKES:
        Cake.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "price": price,
                "image": image,
                "occasion": occasion,
                "sort": sort,
                "is_active": True,
                "description": f"{name} — для повода «{occasion.lower()}». Состав и вес обсуждаются с пекарем.",
            },
        )
    print(f"тортов в каталоге: {Cake.objects.count()}")


def seed_promo():
    PromoCode.objects.update_or_create(
        code="WELCOME", defaults={"percent": 10, "active": True}
    )
    print(f"промокодов: {PromoCode.objects.count()}")


def seed_admin():
    user, created = User.objects.get_or_create(
        phone=DEMO_ADMIN["phone"],
        defaults={"name": DEMO_ADMIN["name"]},
    )
    if created:
        user.is_staff = True
        user.is_superuser = True
        user.set_password(DEMO_ADMIN["password"])
        user.save()
        print(f"админ создан: {user.phone} / {DEMO_ADMIN['password']}")
    else:
        print(f"админ уже есть: {user.phone} (пароль не трогаем)")
    return user


def seed_customer():
    user, created = User.objects.get_or_create(
        phone=DEMO_CUSTOMER["phone"],
        defaults={"name": DEMO_CUSTOMER["name"], "email": DEMO_CUSTOMER["email"]},
    )
    Profile.objects.get_or_create(
        user=user,
        defaults={
            "default_address": "Москва, ул. Тверская, 1",
            "consent_pdp_at": timezone.now(),
            "consent_pdp_ip": "127.0.0.1",
            "pd_version": settings.PD_VERSION,
        },
    )
    if created:
        print(f"покупатель создан: {user.phone}")
    return user


def seed_orders(user):
    today = date.today()
    demo = [
        {
            "number": "2239400223",
            "status": Order.Status.PAID,
            "spec": {
                "levels": 2,
                "form": 2,
                "topping": 4,
                "berries": 1,
                "decor": 2,
                "inscription": "С днём рождения!",
            },
            "price_items": [
                {"title": "2 уровня", "price": 750},
                {"title": "Круг", "price": 400},
                {"title": "Кленовый сироп", "price": 200},
                {"title": "Ежевика", "price": 400},
                {"title": "Безе", "price": 400},
                {"title": "Надпись", "price": 500},
            ],
            "subtotal": 2550,
            "total": 2550,
            "discount": 0,
            "delivery_date": today + timedelta(days=1),
            "delivery_time": time(12, 0),
            "is_rush": False,
            "rush_amount": 0,
            "address": "Москва, ул. Тверская, 1",
            "comment": "",
            "courier_comment": "звонить за час",
            "utm_source": "yandex",
            "utm_medium": "cpc",
            "utm_campaign": "tor_2026",
            "utm_content": "",
            "utm_term": "",
            "referrer": "https://yandex.ru/",
            "session_key": "demo-session-1",
        },
        {
            "number": "2239400224",
            "status": Order.Status.DELIVERED,
            "spec": {"levels": 1, "form": 1, "topping": 7, "berries": 0, "decor": 0, "inscription": ""},
            "price_items": [
                {"title": "1 уровень", "price": 400},
                {"title": "Квадрат", "price": 600},
            ],
            "subtotal": 1000,
            "total": 1000,
            "discount": 0,
            "delivery_date": today - timedelta(days=3),
            "delivery_time": time(18, 0),
            "is_rush": False,
            "rush_amount": 0,
            "address": "Москва, ул. Тверская, 1",
            "comment": "",
            "courier_comment": "",
            "utm_source": "instagram",
            "utm_medium": "social",
            "utm_campaign": "stories",
            "utm_content": "",
            "utm_term": "",
            "referrer": "https://instagram.com/",
            "session_key": "demo-session-2",
        },
    ]
    for order in demo:
        number = order.pop("number")
        Order.objects.update_or_create(
            number=number,
            defaults={
                **order,
                "user": user,
                "pd_consent_at": timezone.now(),
                "pd_consent_ip": "127.0.0.1",
                "pd_version": settings.PD_VERSION,
            },
        )
    print(f"заказов: {Order.objects.count()}")


def seed_visits(user):
    for index, (source, medium, campaign, path, referrer) in enumerate(VISITS, start=1):
        Visit.objects.update_or_create(
            session_key=f"demo-visit-{index}",
            defaults={
                "utm_source": source,
                "utm_medium": medium,
                "utm_campaign": campaign,
                "landing_path": path,
                "referrer": referrer,
                "user": user,
            },
        )
    print(f"визитов: {Visit.objects.count()}")


def main():
    print("Seed BakeCake: идемпотентный, реальные заказы не трогает")
    seed_admin()
    seed_groups()
    seed_catalog()
    seed_promo()
    user = seed_customer()
    seed_orders(user)
    seed_visits(user)
    print("Готово.")


if __name__ == "__main__":
    main()
