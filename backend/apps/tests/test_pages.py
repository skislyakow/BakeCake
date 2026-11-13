import re
from datetime import date, time

import pytest

from apps.orders.models import Order
from apps.users.models import User


def _user(phone="+79000000001", **extra):
    return User.objects.create_user(phone=phone, **extra)


def _superuser(phone="+79000000002"):
    return User.objects.create_superuser(phone=phone, password="admin")


@pytest.mark.django_db
def test_home_renders_mobile_layout_and_image_attributes(client):
    resp = client.get("/")

    body = resp.content.decode()
    assert resp.status_code == 200
    assert 'name="viewport"' in body
    assert "Style.css" in body
    assert "cake__sticky" in body
    assert 'loading="lazy"' in body
    assert 'alt="Торт ручной работы"' in body
    assert "configurator-draft.js" in body
    assert "cake__preview" in body
    assert 'viewBox="0 0 320 300"' in body

    step3 = re.search(r'<section[^>]*id="step3"[^>]*>', body)
    assert step3 and 'v-if="!SelectedCake"' in step3.group(0)
    assert 'SelectedCake ? \'#step4\' : \'#step3\'' in body
    assert '@click="ClearCake"' in body


@pytest.mark.django_db
def test_lk_and_orders_require_login(client):
    assert client.get("/lk/").status_code == 302
    assert client.get("/orders/").status_code == 302


@pytest.mark.django_db
def test_lk_and_orders_render_for_logged_in_user(client):
    client.force_login(_user())

    lk = client.get("/lk/")
    assert lk.status_code == 200
    assert "Личный кабинет" in lk.content.decode()

    orders = client.get("/orders/")
    assert orders.status_code == 200
    assert "Мои заказы" in orders.content.decode()


@pytest.mark.django_db
def test_admin_index_renders_mobile_styles(client):
    client.force_login(_superuser())

    resp = client.get("/admin/")
    body = resp.content.decode()

    assert resp.status_code == 200
    assert "admin/css/mobile.css" in body
    assert "admin/css/site_theme.css" in body
    assert "admin-brand__badge" in body
    assert "img/Logo.svg" in body
    assert "Сводка" in body


@pytest.mark.django_db
def test_admin_order_change_renders_mobile_styles(client):
    client.force_login(_superuser())
    order = Order.objects.create(
        user=_user(),
        total=1500,
        delivery_date=date(2026, 11, 20),
        delivery_time=time(15, 0),
    )

    resp = client.get(f"/admin/orders/order/{order.pk}/change/")
    body = resp.content.decode()

    assert resp.status_code == 200
    assert "admin/css/mobile.css" in body
    assert "admin/css/site_theme.css" in body


@pytest.mark.django_db
def test_jivo_widget_is_skipped_without_site_id(client, settings):
    settings.JIVO_SITE_ID = ""

    body = client.get("/").content.decode()

    assert "code.jivo.ru" not in body


@pytest.mark.django_db
def test_jivo_widget_renders_with_site_id(client, settings):
    settings.JIVO_SITE_ID = "TestSite42"

    body = client.get("/").content.decode()

    assert "//code.jivo.ru/widget/TestSite42" in body
