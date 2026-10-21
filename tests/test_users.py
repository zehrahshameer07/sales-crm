import uuid

from fastapi.testclient import TestClient

from app.main import app

from .conftest import PASSWORD, client_for


def new_user(**overrides):
    payload = {"full_name": "Nisha Patel", "email": "nisha@example.com", "role": "salesperson"}
    payload.update(overrides)
    return payload


def test_only_admins_can_manage_users(clients, people):
    for key in ("maya", "ravi"):
        c = clients[key]
        assert c.get("/api/users").status_code == 403
        assert c.post("/api/users", json=new_user()).status_code == 403
        assert c.get(f"/api/users/{people['ravi'].id}").status_code == 403
        assert c.patch(f"/api/users/{people['ravi'].id}", json={"region": "X"}).status_code == 403
        assert c.post(f"/api/users/{people['ravi'].id}/reset-password").status_code == 403


def test_admin_creates_user_with_generated_temporary_password(clients):
    response = clients["admin"].post("/api/users", json=new_user())
    assert response.status_code == 201
    body = response.json()
    uuid.UUID(body["id"])                                   # IDs are UUIDs
    assert body["must_change_password"] is True and body["temporary_password"]
    # the new person can log in with it, but must change it first
    client = TestClient(app)
    assert client.post("/api/auth/login", json={"email": "nisha@example.com",
                                                 "password": body["temporary_password"]}).status_code == 200
    assert client.get("/api/activities").status_code == 403


def test_admin_can_choose_the_initial_password(clients):
    response = clients["admin"].post("/api/users", json=new_user(password="Chosen-Pass-2026"))
    assert response.status_code == 201 and response.json()["temporary_password"] is None
    assert TestClient(app).post("/api/auth/login", json={"email": "nisha@example.com",
                                                          "password": "Chosen-Pass-2026"}).status_code == 200


def test_duplicate_email_is_a_conflict_ignoring_case(clients):
    admin = clients["admin"]
    assert admin.post("/api/users", json=new_user()).status_code == 201
    assert admin.post("/api/users", json=new_user(email="NISHA@Example.com", full_name="Other Person")).status_code == 409
    assert admin.post("/api/users", json=new_user(email="ravi@example.com", full_name="Dup Ravi")).status_code == 409


def test_duplicate_employee_code_is_a_conflict(clients):
    admin = clients["admin"]
    assert admin.post("/api/users", json=new_user(employee_code="E-100")).status_code == 201
    assert admin.post("/api/users", json=new_user(email="b@example.com", employee_code="E-100")).status_code == 409


def test_user_validation(clients, people):
    admin = clients["admin"]
    assert admin.post("/api/users", json=new_user(email="not-an-email")).status_code == 422
    assert admin.post("/api/users", json=new_user(full_name="A")).status_code == 422
    assert admin.post("/api/users", json=new_user(role="superuser")).status_code == 422
    assert admin.post("/api/users", json=new_user(password="short1")).status_code == 422
    assert admin.post("/api/users", json=new_user(phone="abc")).status_code == 422
    assert admin.post("/api/users", json=new_user(manager_id=str(uuid.uuid4()))).status_code == 422
    # a salesperson can't be someone's manager
    assert admin.post("/api/users", json=new_user(manager_id=str(people["ravi"].id))).status_code == 422
    assert admin.post("/api/users", json=new_user(manager_id=str(people["maya"].id))).status_code == 201


def test_list_filter_and_paginate(clients):
    admin = clients["admin"]
    page = admin.get("/api/users", params={"page_size": 2}).json()
    assert page["total"] == 6 and len(page["items"]) == 2 and page["pages"] == 3
    assert [u["role"] for u in admin.get("/api/users", params={"role": "manager"}).json()["items"]] == ["manager"] * 2
    assert admin.get("/api/users", params={"search": "ravi"}).json()["total"] == 1
    assert admin.get("/api/users", params={"search": "%"}).json()["total"] == 0     # wildcards are escaped
    assert "password_hash" not in str(admin.get("/api/users").json())


def test_unknown_or_malformed_ids(clients):
    admin = clients["admin"]
    assert admin.get(f"/api/users/{uuid.uuid4()}").status_code == 404
    assert admin.get("/api/users/123").status_code == 422          # sequential integer ids don't exist


def test_update_user_and_manager_rules(clients, people):
    admin = clients["admin"]
    ok = admin.patch(f"/api/users/{people['ravi'].id}", json={"manager_id": str(people["mohan"].id), "region": "South"})
    assert ok.status_code == 200 and ok.json()["manager_name"] == "Mohan Manager"
    assert admin.patch(f"/api/users/{people['ravi'].id}", json={"manager_id": str(people["riya"].id)}).status_code == 422
    assert admin.patch(f"/api/users/{people['ravi'].id}", json={"email": "riya@example.com"}).status_code == 409
    assert admin.patch(f"/api/users/{people['ravi'].id}", json={"full_name": None}).status_code == 422
    # a manager with a team can't be turned into a salesperson
    assert admin.patch(f"/api/users/{people['maya'].id}", json={"role": "salesperson"}).status_code == 409


def test_admin_safety_rules(clients, people):
    admin = clients["admin"]
    assert admin.patch(f"/api/users/{people['admin'].id}", json={"is_active": False}).status_code == 409
    assert admin.patch(f"/api/users/{people['admin'].id}", json={"role": "manager"}).status_code == 409
    second = admin.post("/api/users", json=new_user(email="boss@example.com", role="admin", password="Another-Admin-99")).json()
    other = client_for(people["admin"])
    assert other.patch(f"/api/users/{second['id']}", json={"is_active": False}).status_code == 200


def test_reset_password_forces_a_change(clients, people):
    response = clients["admin"].post(f"/api/users/{people['ravi'].id}/reset-password")
    assert response.status_code == 200
    temp = response.json()["temporary_password"]
    assert TestClient(app).post("/api/auth/login", json={"email": "ravi@example.com", "password": PASSWORD}).status_code == 401
    fresh = TestClient(app)
    assert fresh.post("/api/auth/login", json={"email": "ravi@example.com", "password": temp}).status_code == 200
    assert fresh.get("/api/activities").status_code == 403


def test_user_options_are_scoped_by_role(clients, people):
    names = lambda key: sorted(u["full_name"] for u in clients[key].get("/api/users/options").json())  # noqa: E731
    assert names("ravi") == ["Ravi Rep"]
    assert names("maya") == ["Maya Manager", "Ravi Rep", "Riya Rep"]
    assert len(names("admin")) == 6
