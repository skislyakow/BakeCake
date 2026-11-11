import pytest

from apps.pricing.models import Option, OptionGroup


@pytest.mark.django_db
def test_configurator_returns_preview_key(client):
    levels = OptionGroup.objects.create(code="levels", title="Количество уровней", is_required=True, sort=1)
    option = Option.objects.create(
        group=levels,
        title="2 уровня",
        price_delta=750,
        preview_key="level_2",
        sort=1,
    )

    resp = client.get("/api/configurator/")

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["groups"][0]["options"] == [
        {
            "id": option.pk,
            "title": "2 уровня",
            "price_delta": 750,
            "preview_key": "level_2",
        }
    ]


@pytest.mark.django_db
def test_configurator_preview_key_is_optional(client):
    levels = OptionGroup.objects.create(code="levels", title="Количество уровней", is_required=True, sort=1)
    Option.objects.create(group=levels, title="1 уровень", price_delta=400, sort=1)

    resp = client.get("/api/configurator/")

    assert resp.json()["groups"][0]["options"][0]["preview_key"] == ""
