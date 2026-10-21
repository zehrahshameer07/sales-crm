from datetime import timedelta

import jwt
from fastapi.testclient import TestClient

from app import security
from app.config import settings
from app.enums import UserRole
from app.main import app
from app.models import User
from app.timeutil import utcnow

from .conftest import PASSWORD, client_for, make_user


def login(client, email, password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_login_success_sets_secure_cookie_and_returns_user(people):
    client = TestClient(app)
    response = login(client, "ravi@example.com")
    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Ravi Rep" and body["role"] == "salesperson"
    assert "password_hash" not in body and "temporary_password" not in body
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert client.get("/api/auth/me").json()["email"] == "ravi@example.com"


def test_login_email_is_case_insensitive(people):
    assert login(TestClient(app), "  RAVI@Example.com ").status_code == 200


def test_wrong_password_and_unknown_email_give_the_same_message(people):
    client = TestClient(app)
    wrong = login(client, "ravi@example.com", "not-the-password-1")
    unknown = login(client, "nobody@example.com")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_account_locks_after_repeated_failures(people, db):
    client = TestClient(app)
    codes = [login(client, "ravi@example.com", "wrong-password-1").status_code for _ in range(5)]
    assert codes == [401, 401, 401, 401, 429]
    locked = login(client, "ravi@example.com")            # even the right password is refused while locked
    assert locked.status_code == 429 and "Retry-After" in locked.headers
    db.expire_all()
    assert db.query(User).filter_by(email="ravi@example.com").one().is_locked


def test_unknown_email_is_throttled_too(people):
    client = TestClient(app)
    codes = [login(client, "ghost@example.com", "whatever-pass-1").status_code for _ in range(7)]
    assert codes[:5] == [401] * 5 and codes[5:] == [429, 429]


def test_admin_can_unlock(clients, people):
    anon = TestClient(app)
    for _ in range(5):
        login(anon, "ravi@example.com", "wrong-password-1")
    assert login(anon, "ravi@example.com").status_code == 429
    assert clients["admin"].post(f"/api/users/{people['ravi'].id}/unlock").status_code == 200
    assert login(anon, "ravi@example.com").status_code == 200


def test_ip_rate_limit(people, monkeypatch):
    monkeypatch.setattr(settings, "login_ip_limit", 3)
    client = TestClient(app)
    codes = [login(client, f"user{i}@example.com").status_code for i in range(5)]
    assert codes[:3] == [401, 401, 401] and codes[3:] == [429, 429]


def test_deactivated_user_gets_403_only_with_the_right_password(db):
    make_user(db, "Gone Person", UserRole.SALESPERSON, is_active=False)
    client = TestClient(app)
    assert login(client, "gone@example.com", "wrong-password-1").status_code == 401
    assert login(client, "gone@example.com").status_code == 403


def test_protected_routes_need_login():
    client = TestClient(app)
    for path in ("/api/auth/me", "/api/activities", "/api/stats/overview", "/api/users/options"):
        assert client.get(path).status_code == 401


def test_logout_clears_the_cookie(clients):
    client = clients["ravi"]
    response = client.post("/api/auth/logout")
    assert response.status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_tampered_or_expired_tokens_are_rejected(people):
    client = TestClient(app)
    client.cookies.set(settings.cookie_name, "not-a-token")
    assert client.get("/api/auth/me").status_code == 401

    forged = jwt.encode({"sub": str(people["admin"].id), "iat": utcnow(), "exp": utcnow() + timedelta(hours=1)},
                        "some-other-secret-some-other-secret-1234", algorithm="HS256")
    client.cookies.set(settings.cookie_name, forged)
    assert client.get("/api/auth/me").status_code == 401

    expired = jwt.encode({"sub": str(people["admin"].id), "iat": utcnow() - timedelta(hours=2),
                          "exp": utcnow() - timedelta(hours=1)}, settings.secret_key, algorithm="HS256")
    client.cookies.set(settings.cookie_name, expired)
    assert client.get("/api/auth/me").status_code == 401


def test_deactivating_a_user_cuts_off_their_session_immediately(clients, people):
    assert clients["ravi"].get("/api/auth/me").status_code == 200
    assert clients["admin"].patch(f"/api/users/{people['ravi'].id}", json={"is_active": False}).status_code == 200
    assert clients["ravi"].get("/api/auth/me").status_code == 401


def test_changing_password_logs_out_other_sessions(people):
    first, second = client_for(people["ravi"]), client_for(people["ravi"])
    response = first.post("/api/auth/change-password",
                          json={"current_password": PASSWORD, "new_password": "Brand-New-Pass-77"})
    assert response.status_code == 200
    assert first.get("/api/auth/me").status_code == 200       # got a fresh cookie
    assert second.get("/api/auth/me").status_code == 401      # old token no longer valid
    assert login(TestClient(app), "ravi@example.com", "Brand-New-Pass-77").status_code == 200


def test_change_password_rules(clients):
    client = clients["ravi"]
    assert client.post("/api/auth/change-password",
                       json={"current_password": "wrong-password-1", "new_password": "Brand-New-Pass-77"}).status_code == 403
    assert client.post("/api/auth/change-password",
                       json={"current_password": PASSWORD, "new_password": "short1"}).status_code == 422
    assert client.post("/api/auth/change-password",
                       json={"current_password": PASSWORD, "new_password": PASSWORD}).status_code == 422
    assert client.post("/api/auth/change-password",
                       json={"current_password": PASSWORD, "new_password": "onlyletterspassword"}).status_code == 422


def test_must_change_password_blocks_everything_else(db):
    user = make_user(db, "Newbie Person", UserRole.SALESPERSON, must_change_password=True)
    client = client_for(user)
    assert client.get("/api/auth/me").status_code == 200
    blocked = client.get("/api/activities")
    assert blocked.status_code == 403 and blocked.json()["code"] == "password_change_required"
    assert client.post("/api/auth/change-password",
                       json={"current_password": PASSWORD, "new_password": "Fresh-Start-4242"}).status_code == 200
    assert client.get("/api/activities").status_code == 200


def test_passwords_are_hashed_with_argon2(people):
    assert people["ravi"].password_hash.startswith("$argon2id$")
    assert PASSWORD not in people["ravi"].password_hash
    assert security.verify_password(people["ravi"].password_hash, PASSWORD)
    assert not security.verify_password(people["ravi"].password_hash, "nope")


def test_auth_config_hides_demo_accounts_by_default():
    body = TestClient(app).get("/api/auth/config").json()
    assert body["demo_accounts"] == [] and body["password_min_length"] == 10
