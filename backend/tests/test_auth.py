"""Registration, login, logout, and current-user behaviour."""

from sqlalchemy import select

from app.models.enums import UserRole
from app.models.user import User
from tests.conftest import create_user, unique_email


def _registration_payload(**overrides) -> dict:
    payload = {
        "email": unique_email("shopper"),
        "password": "StrongPass!2026",
        "first_name": "Hina",
        "last_name": "Malik",
        "phone": "+92 300 1234567",
    }
    payload.update(overrides)
    return payload


def test_register_creates_a_customer_and_returns_no_password_hash(client, db):
    payload = _registration_payload()

    response = client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == payload["email"]
    assert body["role"] == UserRole.CUSTOMER
    assert body["is_active"] is True
    assert body["is_verified"] is False
    # The hash must never be serialised, under any key spelling.
    assert "password_hash" not in body
    assert "password" not in body


def test_register_stores_an_argon2_hash_not_the_plaintext(client, db):
    payload = _registration_payload()

    client.post("/api/v1/auth/register", json=payload)

    user = db.execute(select(User).where(User.email == payload["email"])).scalar_one()
    assert user.password_hash != payload["password"]
    assert user.password_hash.startswith("$argon2")


def test_register_normalises_email_case(client, db):
    payload = _registration_payload(email="MiXeD.Case@example.com")

    response = client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 201
    assert response.json()["email"] == "mixed.case@example.com"


def test_register_rejects_a_duplicate_email_case_insensitively(client, db):
    payload = _registration_payload(email="dupe@example.com")
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201

    clash = _registration_payload(email="DUPE@example.com")
    response = client.post("/api/v1/auth/register", json=clash)

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_register_rejects_a_short_password(client, db):
    response = client.post("/api/v1/auth/register", json=_registration_payload(password="short"))
    assert response.status_code == 422


def test_register_sets_an_http_only_session_cookie(client, db):
    response = client.post("/api/v1/auth/register", json=_registration_payload())

    cookie_header = response.headers["set-cookie"]
    assert "rg_access_token=" in cookie_header
    assert "HttpOnly" in cookie_header
    assert "Path=/" in cookie_header


def test_login_succeeds_and_records_last_login(client, db):
    user, password = create_user(db, UserRole.CUSTOMER)
    assert user.last_login_at is None

    response = client.post("/api/v1/auth/login", json={"email": user.email, "password": password})

    assert response.status_code == 200, response.text
    assert response.json()["email"] == user.email
    db.refresh(user)
    assert user.last_login_at is not None


def test_login_is_case_insensitive_on_email(client, db):
    user, password = create_user(db, UserRole.CUSTOMER)

    response = client.post(
        "/api/v1/auth/login", json={"email": user.email.upper(), "password": password}
    )

    assert response.status_code == 200


def test_login_rejects_a_wrong_password(client, db):
    user, _ = create_user(db, UserRole.CUSTOMER)

    response = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "WrongPass!2026"}
    )

    assert response.status_code == 401


def test_login_does_not_reveal_whether_an_email_is_registered(client, db):
    user, _ = create_user(db, UserRole.CUSTOMER)

    wrong_password = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "WrongPass!2026"}
    )
    unknown_email = client.post(
        "/api/v1/auth/login",
        json={"email": unique_email("ghost"), "password": "WrongPass!2026"},
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json()["detail"] == unknown_email.json()["detail"]


def test_login_rejects_a_deactivated_account(client, db):
    user, password = create_user(db, UserRole.CUSTOMER)
    user.is_active = False
    db.commit()

    response = client.post("/api/v1/auth/login", json={"email": user.email, "password": password})

    assert response.status_code == 401
    assert "deactivated" in response.json()["detail"]


def test_me_requires_authentication(client, db):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_returns_the_signed_in_user(customer_client, db):
    response = customer_client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["role"] == UserRole.CUSTOMER
    assert "password_hash" not in response.json()


def test_me_rejects_a_tampered_token(client, db):
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert response.status_code == 401


def test_logout_clears_the_session(customer_client, db):
    assert customer_client.get("/api/v1/auth/me").status_code == 200

    logout = customer_client.post("/api/v1/auth/logout")

    assert logout.status_code == 200
    customer_client.cookies.clear()
    assert customer_client.get("/api/v1/auth/me").status_code == 401


def test_login_is_limited_to_five_attempts_per_minute(client):
    from app.core.rate_limit import _auth_events

    _auth_events.clear()
    payload = {"email": unique_email("limited"), "password": "WrongPass!2026"}
    responses = [client.post("/api/v1/auth/login", json=payload) for _ in range(6)]

    assert [response.status_code for response in responses[:5]] == [401] * 5
    assert responses[5].status_code == 429
    assert responses[5].headers["retry-after"] == "60"


def test_register_is_rate_limited(client):
    from app.core.rate_limit import _auth_events

    _auth_events.clear()
    payloads = [
        _registration_payload(email=unique_email("limited-register"))
        for _ in range(6)
    ]
    responses = [client.post("/api/v1/auth/register", json=payload) for payload in payloads]

    assert [response.status_code for response in responses[:5]] == [201] * 5
    assert responses[5].status_code == 429


def test_security_headers_are_added(client):
    response = client.get("/api/v1/auth/me")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["x-frame-options"] == "DENY"


def test_admin_endpoint_requires_authentication_and_rejects_customers(client, customer_client):
    path = "/api/v1/admin/analytics/dashboard"
    assert client.get(path).status_code == 401
    assert customer_client.get(path).status_code == 403
