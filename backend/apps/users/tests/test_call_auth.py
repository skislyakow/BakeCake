import json
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from apps.users import zvonok
from apps.users.models import PhoneConfirm, Profile, User

PHONE = "+79005551122"
PHONE_DIGITS = "79005551122"
NUMBER = "8 800 555-35-35"
SECRET = "zvonok-test-secret"


@pytest.fixture
def call_mode(settings, monkeypatch):
    settings.AUTH_MODE = "call"
    settings.ZVONOK_API_KEY = "test-key"
    settings.ZVONOK_API_SECRET = SECRET
    settings.ZVONOK_VERIFY_URL = "https://zvonok.example/verify"
    settings.ZVONOK_SIGNATURE_HEADER = "X-Zvonok-Signature"
    settings.ZVONOK_VERIFY_NUMBER = NUMBER
    settings.PHONE_CONFIRM_TTL_MINUTES = 5
    settings.PHONE_CONFIRM_MAX_PENDING = 3
    settings.PHONE_CONFIRM_MAX_PER_HOUR = 10

    calls = []

    def fake_start(*, phone, session_id):
        calls.append((phone, session_id))
        return "zv-1"

    monkeypatch.setattr(zvonok, "start_verification", fake_start)
    return calls


def _login(client, phone=PHONE, consent=True):
    return client.post(
        "/api/auth/login/",
        data=json.dumps({"phone": phone, "consent_pdp": consent}),
        content_type="application/json",
    )


def _postback(client, payload, signature=None, header="HTTP_X_ZVONOK_SIGNATURE"):
    raw = json.dumps(payload).encode("utf-8")
    kwargs = {header: signature if signature is not None else zvonok.signature_for(raw)}
    return client.post(
        "/api/auth/verify/postback/",
        data=raw,
        content_type="application/json",
        **kwargs,
    )


def _pending(phone=PHONE, **extra):
    extra.setdefault("expires_at", timezone.now() + timedelta(minutes=5))
    return PhoneConfirm.objects.create(phone=phone, **extra)


@pytest.mark.django_db
def test_call_login_returns_pending_without_session(client, call_mode):
    resp = _login(client)

    data = resp.json()
    assert resp.status_code == 200
    assert data["ok"] is True
    assert data["status"] == "pending"
    assert data["number"] == NUMBER
    assert data["expires_in"] == 300
    assert data["token"]
    assert client.session.get("_auth_user_id") is None

    record = PhoneConfirm.objects.get()
    assert record.phone == PHONE
    assert record.status == PhoneConfirm.Status.PENDING
    assert record.zvonok_id == "zv-1"
    assert call_mode == [(PHONE, data["token"])]
    assert User.objects.filter(phone=PHONE).exists()


@pytest.mark.django_db
def test_call_login_records_consent(client, call_mode):
    _login(client, consent=True)

    profile = Profile.objects.get(user__phone=PHONE)
    assert profile.consent_pdp_at is not None
    assert profile.pd_version


@pytest.mark.django_db
def test_call_login_does_not_record_consent_without_checkbox(client, call_mode):
    _login(client, consent=False)

    profile = Profile.objects.get(user__phone=PHONE)
    assert profile.consent_pdp_at is None


@pytest.mark.django_db
def test_call_login_limits_pending_requests(client, call_mode):
    for _ in range(3):
        _pending()

    resp = _login(client)

    assert resp.status_code == 429
    assert resp.json()["ok"] is False
    assert PhoneConfirm.objects.count() == 3


@pytest.mark.django_db
def test_call_login_limits_requests_per_hour(client, call_mode):
    for _ in range(10):
        _pending(status=PhoneConfirm.Status.EXPIRED)

    resp = _login(client)

    assert resp.status_code == 429
    assert resp.json()["ok"] is False


@pytest.mark.django_db
def test_demo_and_off_modes_keep_expected_login_behavior(client, settings):
    settings.AUTH_MODE = "demo"
    demo = _login(client)
    assert demo.status_code == 200
    assert demo.json()["user"]["phone"] == PHONE

    client.logout()
    settings.AUTH_MODE = "off"
    off = _login(client)
    assert off.status_code == 403
    assert off.json()["ok"] is False


@pytest.mark.django_db
def test_provider_failure_rejects_pending_record(client, call_mode, monkeypatch):
    def broken_start(**_kwargs):
        raise zvonok.ZvonokError("provider is down")

    monkeypatch.setattr(zvonok, "start_verification", broken_start)

    resp = _login(client)

    assert resp.status_code == 502
    assert resp.json()["ok"] is False
    assert PhoneConfirm.objects.get().status == PhoneConfirm.Status.REJECTED
    assert client.session.get("_auth_user_id") is None


@pytest.mark.django_db
def test_postback_without_signature_is_rejected(client, call_mode):
    _login(client)
    record = PhoneConfirm.objects.get()

    resp = client.post(
        "/api/auth/verify/postback/",
        data=json.dumps({"phone": PHONE_DIGITS, "status": "confirmed"}),
        content_type="application/json",
    )

    assert resp.status_code == 403
    record.refresh_from_db()
    assert record.status == PhoneConfirm.Status.PENDING


@pytest.mark.django_db
def test_postback_with_wrong_signature_is_rejected(client, call_mode):
    _login(client)
    record = PhoneConfirm.objects.get()

    resp = _postback(
        client,
        {"phone": PHONE_DIGITS, "token": str(record.token), "status": "confirmed"},
        signature="sha256=deadbeef",
    )

    assert resp.status_code == 403
    record.refresh_from_db()
    assert record.status == PhoneConfirm.Status.PENDING


@pytest.mark.django_db
def test_postback_confirms_and_status_opens_session(client, call_mode):
    _login(client)
    record = PhoneConfirm.objects.get()

    resp = _postback(
        client,
        {
            "phone": PHONE_DIGITS,
            "session_id": str(record.token),
            "status": "confirmed",
        },
    )

    assert resp.status_code == 200
    record.refresh_from_db()
    assert record.status == PhoneConfirm.Status.CONFIRMED

    status = client.get(f"/api/auth/verify/status/?token={record.token}")
    assert status.status_code == 200
    assert status.json()["ok"] is True
    assert status.json()["status"] == "confirmed"
    assert status.json()["user"]["phone"] == PHONE
    assert client.session.get("_auth_user_id") is not None

    record.refresh_from_db()
    assert record.session_issued is True


@pytest.mark.django_db
def test_status_is_idempotent_after_session_is_issued(client, call_mode):
    _login(client)
    record = PhoneConfirm.objects.get()
    _postback(
        client,
        {"phone": PHONE_DIGITS, "session_id": str(record.token), "status": "confirmed"},
    )

    first = client.get(f"/api/auth/verify/status/?token={record.token}")
    second = client.get(f"/api/auth/verify/status/?token={record.token}")

    assert first.json()["status"] == "confirmed"
    assert second.json()["status"] == "confirmed"


@pytest.mark.django_db
def test_repeated_postback_does_not_change_confirmed_record(client, call_mode):
    _login(client)
    record = PhoneConfirm.objects.get()
    payload = {
        "phone": PHONE_DIGITS,
        "session_id": str(record.token),
        "status": "confirmed",
    }

    _postback(client, payload)
    _postback(client, payload)

    record.refresh_from_db()
    assert record.status == PhoneConfirm.Status.CONFIRMED
    assert record.attempts == 1


@pytest.mark.django_db
def test_postback_can_be_called_without_csrf_token(call_mode):
    csrf_client = Client(enforce_csrf_checks=True)
    _login(csrf_client)
    record = PhoneConfirm.objects.get()

    resp = _postback(
        csrf_client,
        {"phone": PHONE_DIGITS, "session_id": str(record.token), "status": "confirmed"},
    )

    assert resp.status_code == 200


@pytest.mark.django_db
def test_postback_with_non_success_status_rejects_record(client, call_mode):
    _login(client)
    record = PhoneConfirm.objects.get()

    resp = _postback(
        client,
        {"phone": PHONE_DIGITS, "session_id": str(record.token), "status": "failed"},
    )

    assert resp.status_code == 200
    record.refresh_from_db()
    assert record.status == PhoneConfirm.Status.REJECTED
    assert record.attempts == 1


@pytest.mark.django_db
def test_expired_record_cannot_be_confirmed(client, call_mode):
    record = _pending(expires_at=timezone.now() - timedelta(seconds=1))

    resp = _postback(
        client,
        {"phone": PHONE_DIGITS, "session_id": str(record.token), "status": "confirmed"},
    )

    assert resp.status_code == 200
    record.refresh_from_db()
    assert record.status == PhoneConfirm.Status.EXPIRED

    status = client.get(f"/api/auth/verify/status/?token={record.token}")
    assert status.json()["status"] == "expired"


@pytest.mark.django_db
def test_postback_for_other_phone_does_not_confirm(client, call_mode):
    record = _pending()

    resp = _postback(
        client,
        {"phone": "79001112233", "session_id": str(record.token), "status": "confirmed"},
    )

    assert resp.status_code == 200
    record.refresh_from_db()
    assert record.status == PhoneConfirm.Status.PENDING


@pytest.mark.django_db
def test_postback_accepts_provider_aliases(client, call_mode):
    record = _pending()

    resp = _postback(
        client,
        {"caller": PHONE_DIGITS, "token": str(record.token), "result": "success", "call_id": "abc"},
    )

    assert resp.status_code == 200
    record.refresh_from_db()
    assert record.status == PhoneConfirm.Status.CONFIRMED
    assert record.zvonok_id == "abc"


@pytest.mark.django_db
def test_status_unknown_or_missing_token(client, call_mode):
    missing = client.get("/api/auth/verify/status/")
    unknown = client.get("/api/auth/verify/status/?token=00000000-0000-0000-0000-000000000000")
    broken = client.get("/api/auth/verify/status/?token=not-a-uuid")

    assert missing.status_code == 400
    assert unknown.status_code == 404
    assert broken.status_code == 404


@pytest.mark.django_db
def test_call_endpoints_do_not_exist_in_demo_mode(client, settings):
    settings.AUTH_MODE = "demo"

    status = client.get("/api/auth/verify/status/?token=whatever")
    postback = client.post(
        "/api/auth/verify/postback/",
        data=json.dumps({"phone": PHONE_DIGITS, "status": "confirmed"}),
        content_type="application/json",
    )

    assert status.status_code == 404
    assert postback.status_code == 404


@pytest.mark.django_db
def test_registration_modal_exposes_auth_mode(client, settings):
    settings.AUTH_MODE = "call"

    body = client.get("/").content.decode()

    assert 'data-auth-mode="call"' in body
    assert "Позвоните на номер" in body
