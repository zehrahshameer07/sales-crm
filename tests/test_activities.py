import uuid
from datetime import timedelta

from app.timeutil import today

from .conftest import activity_payload, create_activity


def day(offset=0):
    return (today() + timedelta(days=offset)).isoformat()


def test_create_defaults(clients, people):
    a = create_activity(clients["ravi"], notes="Liked the demo")
    uuid.UUID(a["id"])
    assert a["status"] == "pending" and a["start_date"] == day()
    assert a["owner"]["id"] == str(people["ravi"].id)
    assert a["created_by_name"] == "Ravi Rep" and a["updated_by_name"] == "Ravi Rep"
    assert a["created_at"].endswith("Z") or "+00:00" in a["created_at"]     # UTC timestamps
    assert a["permissions"] == {"can_edit": True, "can_change_status": True, "can_set_end_date": False}

def test_only_admin_can_choose_initial_status(clients):
    salesperson_response = clients["ravi"].post(
        "/api/activities",
        json=activity_payload("Salesperson Status Test", status="completed"),
    )
    assert salesperson_response.status_code == 403

    admin_response = clients["admin"].post(
        "/api/activities",
        json=activity_payload("Admin Status Test", status="completed"),
    )
    assert admin_response.status_code == 201
    assert admin_response.json()["status"] == "completed"


def test_create_validation(clients):
    r = clients["ravi"]
    bad = [
        activity_payload("A"),
        activity_payload(activity_type="meeting"),
        activity_payload(product_interested="other"),
        activity_payload(contact="abc"),
        activity_payload(notes="x" * 501),
        activity_payload(start_date="31-12-2026"),
        activity_payload(start_date=day(1)),
        activity_payload(start_date=day(-3), follow_up_date=day(-5)),
    ]
    codes = [r.post("/api/activities", json=p).status_code for p in bad]
    assert codes == [422] * len(bad)


def test_text_is_cleaned_and_blanks_become_null(clients):
    a = create_activity(clients["ravi"], "  Spice    Garden ", contact="", location="  ", notes="")
    assert a["customer_name"] == "Spice Garden"
    assert a["contact"] is None and a["location"] is None and a["notes"] is None


def test_backdated_start_date_and_follow_up(clients):
    a = create_activity(clients["ravi"], start_date=day(-2), follow_up_date=day(3), follow_up_notes="Call back")
    assert a["start_date"] == day(-2) and a["follow_up_date"] == day(3) and a["follow_up_notes"] == "Call back"


def test_non_admins_cannot_log_for_someone_else(clients, people):
    r = clients["ravi"].post("/api/activities", json=activity_payload(owner_id=str(people["riya"].id)))
    assert r.status_code == 403
    ok = clients["admin"].post("/api/activities", json=activity_payload(owner_id=str(people["riya"].id)))
    assert ok.status_code == 201 and ok.json()["owner"]["full_name"] == "Riya Rep"
    assert clients["admin"].post("/api/activities", json=activity_payload(owner_id=str(uuid.uuid4()))).status_code == 422


# ----------------------------------------------------------------- scoping
def test_each_role_sees_the_right_activities(clients):
    create_activity(clients["ravi"], "Ravi One")
    create_activity(clients["riya"], "Riya One")
    create_activity(clients["rohan"], "Rohan One")
    create_activity(clients["maya"], "Maya Own")

    def names(key, **params):
        return sorted(a["customer_name"] for a in clients[key].get("/api/activities", params=params).json()["items"])

    assert names("ravi") == ["Ravi One"]
    assert names("maya") == ["Maya Own", "Ravi One", "Riya One"]       # herself + her team only
    assert names("mohan") == ["Rohan One"]                              # Mohan manages Rohan, not Ravi or Riya
    assert names("rohan") == ["Rohan One"]
    assert len(names("admin")) == 4


def test_other_peoples_activities_look_like_they_do_not_exist(clients):
    a = create_activity(clients["ravi"], "Private One")
    for key in ("riya", "rohan", "mohan"):
        c = clients[key]
        assert c.get(f"/api/activities/{a['id']}").status_code == 404
        assert c.patch(f"/api/activities/{a['id']}", json={"notes": "x"}).status_code == 404
        assert c.get(f"/api/activities/{a['id']}/history").status_code == 404
        assert c.post(f"/api/activities/{a['id']}/status", json={"status": "completed"}).status_code == 404
    assert clients["maya"].get(f"/api/activities/{a['id']}").status_code == 200
    assert clients["admin"].get(f"/api/activities/{a['id']}").status_code == 200


def test_ids_are_not_guessable(clients):
    assert clients["ravi"].get("/api/activities/1").status_code == 422
    assert clients["ravi"].get(f"/api/activities/{uuid.uuid4()}").status_code == 404


def test_owner_filter_respects_scope(clients, people):
    create_activity(clients["ravi"], "Ravi One")
    create_activity(clients["riya"], "Riya One")
    maya, admin = clients["maya"], clients["admin"]
    assert len(maya.get("/api/activities", params={"owner_id": str(people["ravi"].id)}).json()["items"]) == 1
    assert maya.get("/api/activities", params={"owner_id": str(people["rohan"].id)}).status_code == 404
    assert len(admin.get("/api/activities", params={"owner_id": str(people["riya"].id)}).json()["items"]) == 1


# ---------------------------------------------------------------- listing
def test_filters_search_sorting_and_pagination(clients):
    r = clients["ravi"]
    create_activity(r, "Old Visit", start_date=day(-10))
    create_activity(r, "Today Visit")
    create_activity(r, "Middle Call", activity_type="call", start_date=day(-5))
    items = r.get("/api/activities").json()["items"]
    assert [a["customer_name"] for a in items] == ["Today Visit", "Middle Call", "Old Visit"]    # newest start first
    assert len(r.get("/api/activities", params={"period": "today"}).json()["items"]) == 1
    assert [a["customer_name"] for a in r.get("/api/activities", params={"activity_type": "call"}).json()["items"]] == ["Middle Call"]
    assert r.get("/api/activities", params={"search": "visit"}).json()["total"] == 2
    assert r.get("/api/activities", params={"search": "%"}).json()["total"] == 0
    assert r.get("/api/activities", params={"from": day(-6), "to": day(-1)}).json()["total"] == 1
    page = r.get("/api/activities", params={"page_size": 2, "page": 2}).json()
    assert page["total"] == 3 and page["pages"] == 2 and len(page["items"]) == 1
    assert r.get("/api/activities", params={"page_size": 500}).status_code == 422
    assert r.get("/api/activities", params={"status": "done"}).status_code == 422
    assert r.get("/api/activities", params={"period": "year"}).status_code == 422


def test_follow_up_filters(clients):
    r = clients["ravi"]
    create_activity(r, "Overdue Cafe", start_date=day(-6), follow_up_date=day(-2))
    create_activity(r, "Today Cafe", follow_up_date=day(0))
    create_activity(r, "Later Cafe", follow_up_date=day(4))
    create_activity(r, "None Cafe")
    def names(kind):
        return [a["customer_name"] for a in r.get("/api/activities", params={"follow_up": kind}).json()["items"]]
    assert names("overdue") == ["Overdue Cafe"]
    assert names("due_today") == ["Today Cafe"]
    assert names("upcoming") == ["Later Cafe"]


# ------------------------------------------------------------- duplicates
def test_duplicate_activities_are_rejected(clients):
    r = clients["ravi"]
    create_activity(r, "Spice Garden")
    for variant in ("Spice Garden", "  spice   garden  ", "SPICE GARDEN"):
        dup = r.post("/api/activities", json=activity_payload(variant))
        assert dup.status_code == 409
        assert "already logged" in dup.json()["detail"]


def test_not_a_duplicate_when_type_day_or_person_differs(clients):
    create_activity(clients["ravi"], "Spice Garden")
    create_activity(clients["ravi"], "Spice Garden", activity_type="call")           # different type
    create_activity(clients["ravi"], "Spice Garden", start_date=day(-1))             # different day
    create_activity(clients["riya"], "Spice Garden")                                 # different salesperson


def test_editing_into_a_duplicate_is_rejected(clients):
    r = clients["ravi"]
    create_activity(r, "Spice Garden")
    other = create_activity(r, "Dosa Corner")
    assert r.patch(f"/api/activities/{other['id']}", json={"customer_name": "spice garden"}).status_code == 409
    assert r.patch(f"/api/activities/{other['id']}", json={"customer_name": "Dosa Corner 2"}).status_code == 200


# ------------------------------------------------------------------ editing
def test_salesperson_edits_own_pending_activity(clients):
    a = create_activity(clients["ravi"])
    r = clients["ravi"].patch(f"/api/activities/{a['id']}", json={"notes": "Updated", "location": "HSR", "contact": ""})
    assert r.status_code == 200
    body = r.json()
    assert body["notes"] == "Updated" and body["location"] == "HSR" and body["contact"] is None
    assert body["updated_at"] >= a["updated_at"]


def test_status_is_not_editable_through_patch(clients):
    a = create_activity(clients["ravi"])
    r = clients["ravi"].patch(f"/api/activities/{a['id']}", json={"status": "completed"})
    assert r.status_code == 200 and r.json()["status"] == "pending"      # unknown field is ignored


def test_edit_validation(clients):
    a = create_activity(clients["ravi"])
    p = f"/api/activities/{a['id']}"
    r = clients["ravi"]
    assert r.patch(p, json={"customer_name": "A"}).status_code == 422
    assert r.patch(p, json={"customer_name": None}).status_code == 422
    assert r.patch(p, json={"start_date": day(2)}).status_code == 422
    assert r.patch(p, json={"follow_up_date": day(-9)}).status_code == 422
    assert r.patch(p, json={"end_date": day(0)}).status_code == 403       # only admins set end dates
    assert clients["admin"].patch(p, json={"end_date": day(0)}).status_code == 422   # not completed


def test_managers_cannot_edit_their_teams_details(clients):
    a = create_activity(clients["ravi"])
    assert clients["maya"].patch(f"/api/activities/{a['id']}", json={"notes": "x"}).status_code == 403
    own = create_activity(clients["maya"], "Maya Own")
    assert clients["maya"].patch(f"/api/activities/{own['id']}", json={"notes": "mine"}).status_code == 200


def test_completed_activities_are_locked_for_everyone_but_admins(clients):
    a = create_activity(clients["ravi"])

    # A manager must move the activity through each status.
    assert clients["maya"].post(
        f"/api/activities/{a['id']}/status",
        json={"status": "in_progress"},
    ).status_code == 200

    assert clients["maya"].post(
        f"/api/activities/{a['id']}/status",
        json={"status": "completed"},
    ).status_code == 200

    # Non-admin users cannot reopen a completed activity.
    assert clients["maya"].post(
        f"/api/activities/{a['id']}/status",
        json={"status": "pending"},
    ).status_code == 403

    assert clients["ravi"].post(
        f"/api/activities/{a['id']}/status",
        json={"status": "pending"},
    ).status_code == 403

    # Admins can reopen it.
    assert clients["admin"].post(
        f"/api/activities/{a['id']}/status",
        json={"status": "pending"},
    ).status_code == 200


def test_admin_can_reassign_and_collisions_are_blocked(clients, people):
    a = create_activity(clients["ravi"], "Spice Garden")
    create_activity(clients["riya"], "Spice Garden")
    assert clients["admin"].patch(f"/api/activities/{a['id']}", json={"owner_id": str(people["riya"].id)}).status_code == 409
    assert clients["admin"].patch(f"/api/activities/{a['id']}", json={"owner_id": str(people["rohan"].id)}).status_code == 200
    assert clients["ravi"].patch(f"/api/activities/{a['id']}", json={"owner_id": str(people["riya"].id)}).status_code == 404


def test_write_rate_limit(clients, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "write_rate_limit", 3)
    codes = [clients["ravi"].post("/api/activities", json=activity_payload(f"Cafe Number {i}")).status_code for i in range(5)]
    assert codes == [201, 201, 201, 429, 429]
