VALID = {
    "customer_name": "Spice Garden",
    "activity_type": "Visit",
    "status": "Pending",
    "notes": "Interested in video menu",
}


def test_create_and_list(client):
    res = client.post("/api/activities", json=VALID)
    assert res.status_code == 201
    body = res.json()
    assert body["id"] == 1 and body["customer_name"] == "Spice Garden"
    assert body["created_at"]

    listing = client.get("/api/activities").json()
    assert len(listing) == 1


def test_newest_first(client):
    client.post("/api/activities", json={**VALID, "customer_name": "First One"})
    client.post("/api/activities", json={**VALID, "customer_name": "Second One"})
    names = [a["customer_name"] for a in client.get("/api/activities").json()]
    assert names == ["Second One", "First One"]


def test_optional_fields_and_blank_to_null(client):
    payload = {**VALID, "contact": "", "location": "  ", "product_interested": "", "notes": ""}
    res = client.post("/api/activities", json=payload)
    assert res.status_code == 201
    body = res.json()
    assert body["contact"] is None and body["location"] is None
    assert body["product_interested"] is None and body["notes"] is None


def test_whitespace_is_trimmed(client):
    res = client.post("/api/activities", json={**VALID, "customer_name": "  Dosa Corner  "})
    assert res.json()["customer_name"] == "Dosa Corner"


def test_validation_rejects_bad_input(client):
    bad_payloads = [
        {**VALID, "customer_name": "A"},                 # too short
        {**VALID, "customer_name": "   "},               # blank
        {**VALID, "status": "Done"},                     # not allowed
        {**VALID, "activity_type": "Email"},             # not allowed
        {**VALID, "contact": "abc"},                     # not a phone number
        {**VALID, "product_interested": "Other"},        # not allowed
        {**VALID, "notes": "x" * 501},                   # too long
    ]
    for payload in bad_payloads:
        assert client.post("/api/activities", json=payload).status_code == 422
    missing = {k: v for k, v in VALID.items() if k != "status"}
    assert client.post("/api/activities", json=missing).status_code == 422
    assert client.get("/api/activities").json() == []


def test_stats(client):
    for status in ["Pending", "Pending", "In Progress", "Completed"]:
        client.post("/api/activities", json={**VALID, "status": status})
    stats = client.get("/api/stats").json()
    assert (stats["total"], stats["pending"], stats["in_progress"], stats["completed"]) == (4, 2, 1, 1)
    assert stats["completion_rate"] == 25


def test_stats_breakdowns(client):
    client.post("/api/activities", json={**VALID, "activity_type": "Call", "product_interested": "Both"})
    client.post("/api/activities", json={**VALID, "activity_type": "Call"})
    client.post("/api/activities", json={**VALID, "activity_type": "Demo", "product_interested": "FreeBees-Play"})
    stats = client.get("/api/stats").json()
    types = {i["label"]: i["count"] for i in stats["by_type"]}
    products = {i["label"]: i["count"] for i in stats["by_product"]}
    assert types == {"Call": 2, "Visit": 0, "Demo": 1, "Follow-up": 0}
    assert products == {"FreeBees-Menu": 0, "FreeBees-Play": 1, "Both": 1, "Not specified": 1}
    days = stats["last_7_days"]
    assert len(days) == 7 and days[-1]["count"] == 3 and sum(d["count"] for d in days) == 3


def test_stats_empty(client):
    stats = client.get("/api/stats").json()
    assert stats["total"] == 0 and stats["completion_rate"] == 0
    assert len(stats["last_7_days"]) == 7


def test_filters(client):
    client.post("/api/activities", json={**VALID, "customer_name": "Tandoor Tales", "status": "Completed"})
    client.post("/api/activities", json={**VALID, "customer_name": "Cafe Brew", "status": "Pending"})
    assert len(client.get("/api/activities?status=Completed").json()) == 1
    assert len(client.get("/api/activities?search=brew").json()) == 1
    assert len(client.get("/api/activities?period=today").json()) == 2
    assert client.get("/api/stats?period=today").json()["total"] == 2


def test_invalid_query_params(client):
    assert client.get("/api/activities?period=year").status_code == 422
    assert client.get("/api/activities?status=Bad").status_code == 422


def test_homepage_served(client):
    res = client.get("/")
    assert res.status_code == 200 and "Sales CRM" in res.text



# ---------- Editing and status rules ----------
def _create(client, **overrides):
    return client.post("/api/activities", json={**VALID, **overrides}).json()["id"]


def test_edit_details(client):
    activity_id = _create(client)
    res = client.patch(f"/api/activities/{activity_id}", json={
        "customer_name": "Spice Garden Deluxe", "location": "Indiranagar", "notes": "",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["customer_name"] == "Spice Garden Deluxe"
    assert body["location"] == "Indiranagar"
    assert body["notes"] is None            # blank clears the field
    assert body["status"] == "Pending"      # untouched fields stay the same


def test_status_moves_forward(client):
    activity_id = _create(client)
    assert client.patch(f"/api/activities/{activity_id}", json={"status": "In Progress"}).status_code == 200
    assert client.patch(f"/api/activities/{activity_id}", json={"status": "Completed"}).status_code == 200


def test_pending_can_jump_to_completed(client):
    activity_id = _create(client)
    assert client.patch(f"/api/activities/{activity_id}", json={"status": "Completed"}).status_code == 200


def test_status_cannot_go_backwards(client):
    done = _create(client, status="Completed")
    for bad in ("Pending", "In Progress"):
        res = client.patch(f"/api/activities/{done}", json={"status": bad})
        assert res.status_code == 400
    assert client.get("/api/activities").json()[0]["status"] == "Completed"

    working = _create(client, status="In Progress")
    assert client.patch(f"/api/activities/{working}", json={"status": "Pending"}).status_code == 400


def test_completed_can_still_edit_notes(client):
    done = _create(client, status="Completed")
    res = client.patch(f"/api/activities/{done}", json={"status": "Completed", "notes": "Signed the contract"})
    assert res.status_code == 200 and res.json()["notes"] == "Signed the contract"


def test_edit_validation_and_not_found(client):
    activity_id = _create(client)
    assert client.patch(f"/api/activities/{activity_id}", json={"customer_name": "A"}).status_code == 422
    assert client.patch(f"/api/activities/{activity_id}", json={"customer_name": None}).status_code == 422
    assert client.patch(f"/api/activities/{activity_id}", json={"status": "Done"}).status_code == 422
    assert client.patch(f"/api/activities/{activity_id}", json={"contact": "abc"}).status_code == 422
    assert client.patch("/api/activities/9999", json={"notes": "x"}).status_code == 404
    


# ---------- Start date / end date ----------
from datetime import date, timedelta


def _day(days_ago):
    return (date.today() - timedelta(days=days_ago)).isoformat()


def test_start_date_defaults_to_today_and_can_be_backdated(client):
    today_id = _create(client)
    past_id = _create(client, start_date=_day(3))
    by_id = {a["id"]: a for a in client.get("/api/activities").json()}
    assert by_id[today_id]["start_date"] == _day(0)
    assert by_id[past_id]["start_date"] == _day(3)
    assert by_id[past_id]["end_date"] is None


def test_start_date_cannot_be_in_the_future(client):
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    assert client.post("/api/activities", json={**VALID, "start_date": tomorrow}).status_code == 400
    assert client.post("/api/activities", json={**VALID, "start_date": "not-a-date"}).status_code == 422
    activity_id = _create(client)
    assert client.patch(f"/api/activities/{activity_id}", json={"start_date": tomorrow}).status_code == 400


def test_end_date_rules(client):
    # only allowed on completed activities, not before start, not in the future
    pending = {**VALID, "start_date": _day(5), "end_date": _day(1)}
    assert client.post("/api/activities", json=pending).status_code == 400
    before = {**VALID, "status": "Completed", "start_date": _day(2), "end_date": _day(4)}
    assert client.post("/api/activities", json=before).status_code == 400
    future = {**VALID, "status": "Completed", "start_date": _day(2),
              "end_date": (date.today() + timedelta(days=1)).isoformat()}
    assert client.post("/api/activities", json=future).status_code == 400
    ok = {**VALID, "status": "Completed", "start_date": _day(5), "end_date": _day(2)}
    res = client.post("/api/activities", json=ok)
    assert res.status_code == 201 and res.json()["end_date"] == _day(2)


def test_completing_sets_end_date_to_today(client):
    activity_id = _create(client, start_date=_day(2))
    done = client.patch(f"/api/activities/{activity_id}", json={"status": "Completed"}).json()
    assert done["end_date"] == _day(0)
    assert _create(client, status="Completed") and client.get("/api/activities").json()[0]["end_date"] == _day(0)


def test_end_date_can_be_edited_after_completing(client):
    activity_id = _create(client, start_date=_day(4))
    client.patch(f"/api/activities/{activity_id}", json={"status": "Completed"})
    res = client.patch(f"/api/activities/{activity_id}", json={"status": "Completed", "end_date": _day(2)})
    assert res.status_code == 200 and res.json()["end_date"] == _day(2)
    assert client.patch(f"/api/activities/{activity_id}", json={"end_date": _day(9)}).status_code == 400  # before start


def test_end_date_on_pending_is_rejected_when_editing(client):
    activity_id = _create(client)
    assert client.patch(f"/api/activities/{activity_id}", json={"end_date": _day(0)}).status_code == 400
    # a blank end date from the form is fine
    assert client.patch(f"/api/activities/{activity_id}", json={"end_date": ""}).status_code == 200


def test_dashboard_and_list_use_start_date(client):
    _create(client, customer_name="Old Visit", start_date=_day(10))
    _create(client, customer_name="Today Visit")
    assert client.get("/api/stats?period=today").json()["total"] == 1
    assert client.get("/api/stats?period=all").json()["total"] == 2
    assert len(client.get("/api/activities?period=today").json()) == 1
    # newest start date first, even though "Old Visit" was logged first and "Today Visit" second
    _create(client, customer_name="Logged Last But Started Earlier", start_date=_day(5))
    names = [a["customer_name"] for a in client.get("/api/activities").json()]
    assert names == ["Today Visit", "Logged Last But Started Earlier", "Old Visit"]
    # the 7-day chart counts by start date too
    days = client.get("/api/stats").json()["last_7_days"]
    assert days[-1]["count"] == 1 and days[1]["count"] == 1      # today, and 5 days ago


def test_time_to_complete_stats(client):
    stats = client.get("/api/stats").json()
    assert stats["avg_days_to_complete"] is None and stats["timed_count"] == 0
    _create(client, status="Completed", start_date=_day(4), end_date=_day(2))   # 2 days
    _create(client, status="Completed", start_date=_day(3), end_date=_day(3))   # same day
    _create(client, status="Completed", start_date=_day(6), end_date=_day(0))   # 6 days
    _create(client)                                                               # not completed: ignored
    stats = client.get("/api/stats").json()
    assert stats["timed_count"] == 3
    assert (stats["fastest_days"], stats["slowest_days"]) == (0, 6)
    assert stats["avg_days_to_complete"] == 2.7