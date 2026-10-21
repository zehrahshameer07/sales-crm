from datetime import timedelta

from app.timeutil import today

from .conftest import create_activity


def day(offset=0):
    return (today() + timedelta(days=offset)).isoformat()


def set_status(client, activity, status, **extra):
    return client.post(f"/api/activities/{activity['id']}/status", json={"status": status, **extra})


def test_salespeople_cannot_change_status(clients):
    a = create_activity(clients["ravi"])
    r = set_status(clients["ravi"], a, "in_progress")
    assert r.status_code == 403
    assert clients["ravi"].get(f"/api/activities/{a['id']}").json()["status"] == "pending"


def test_manager_changes_status_for_their_team_only(clients):
    mine = create_activity(clients["ravi"], "Ravi One")
    theirs = create_activity(clients["rohan"], "Rohan One")
    assert set_status(clients["maya"], mine, "in_progress").status_code == 200
    assert set_status(clients["maya"], theirs, "in_progress").status_code == 404      # not her team: invisible


def test_manager_cannot_approve_their_own_activity(clients):
    own = create_activity(clients["maya"], "Maya Own")
    assert set_status(clients["maya"], own, "in_progress").status_code == 403
    assert set_status(clients["admin"], own, "in_progress").status_code == 200


def test_admin_can_change_any_status(clients):
    a = create_activity(clients["rohan"])
    assert set_status(clients["admin"], a, "in_progress").status_code == 200


def test_status_only_moves_forward(clients):
    a = create_activity(clients["ravi"])
    admin = clients["admin"]
    assert set_status(admin, a, "pending").status_code == 409            # same status
    assert set_status(admin, a, "in_progress").status_code == 200
    assert set_status(admin, a, "pending").status_code == 409            # backwards
    assert set_status(admin, a, "in_progress").status_code == 409
    assert set_status(admin, a, "completed").status_code == 200
    for back in ("pending", "in_progress", "completed"):
        r = set_status(admin, a, back)
        assert r.status_code == 409
    assert set_status(admin, a, "done").status_code == 422


def test_pending_can_jump_to_completed(clients):
    a = create_activity(clients["ravi"])
    assert set_status(clients["admin"], a, "completed").status_code == 200


def test_completing_sets_the_end_date_to_today(clients):
    a = create_activity(clients["ravi"], start_date=day(-3))
    done = set_status(clients["admin"], a, "completed").json()
    assert done["end_date"] == day() and done["days_to_complete"] == 3


def test_completing_with_a_backdated_end_date(clients):
    a = create_activity(clients["ravi"], start_date=day(-5))
    done = set_status(clients["maya"], a, "completed", end_date=day(-2)).json()
    assert done["end_date"] == day(-2) and done["days_to_complete"] == 3


def test_end_date_rules_when_completing(clients):
    a = create_activity(clients["ravi"], start_date=day(-5))
    admin = clients["admin"]
    assert set_status(admin, a, "completed", end_date=day(-9)).status_code == 422     # before start
    assert set_status(admin, a, "completed", end_date=day(1)).status_code == 422      # future
    assert set_status(admin, a, "in_progress", end_date=day(0)).status_code == 422    # only when completing


def test_status_history_is_recorded(clients):
    a = create_activity(clients["ravi"])
    set_status(clients["maya"], a, "in_progress")
    set_status(clients["admin"], a, "completed")
    rows = clients["ravi"].get(f"/api/activities/{a['id']}/history").json()
    assert [(r["from_status"], r["to_status"], r["changed_by_name"]) for r in rows] == [
        (None, "pending", "Ravi Rep"),
        ("pending", "in_progress", "Maya Manager"),
        ("in_progress", "completed", "Alice Admin"),
    ]


def test_updated_fields_track_who_and_when(clients):
    a = create_activity(clients["ravi"])
    after = set_status(clients["maya"], a, "in_progress").json()
    assert after["updated_by_name"] == "Maya Manager" and after["created_by_name"] == "Ravi Rep"
    assert after["updated_at"] >= a["created_at"]


def test_permission_flags_follow_the_role_and_state(clients):
    a = create_activity(clients["ravi"])
    flags = lambda key: clients[key].get(f"/api/activities/{a['id']}").json()["permissions"]  # noqa: E731
    assert flags("ravi") == {"can_edit": True, "can_change_status": False, "can_set_end_date": False}
    assert flags("maya") == {"can_edit": False, "can_change_status": True, "can_set_end_date": False}
    assert flags("admin") == {"can_edit": True, "can_change_status": True, "can_set_end_date": False}
    set_status(clients["admin"], a, "completed")
    assert flags("ravi")["can_edit"] is False
    assert flags("maya")["can_change_status"] is False
    assert flags("admin") == {"can_edit": True, "can_change_status": False, "can_set_end_date": True}
