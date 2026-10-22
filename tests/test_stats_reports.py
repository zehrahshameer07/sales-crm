from datetime import timedelta

from fastapi.testclient import TestClient

from app.main import app
from app.services.exports import csv_safe
from app.timeutil import today

from .conftest import create_activity


def day(offset=0):
    return (today() + timedelta(days=offset)).isoformat()


def complete(client, activity, end=None):
    started = client.post(
        f"/api/activities/{activity['id']}/status",
        json={"status": "in_progress"},
    )
    assert started.status_code == 200, started.text

    body = {"status": "completed"}
    if end:
        body["end_date"] = end

    response = client.post(
        f"/api/activities/{activity['id']}/status",
        json=body,
    )
    assert response.status_code == 200, response.text
    return response



def seed_data(clients):
    a = create_activity(clients["ravi"], "Ravi Done A", start_date=day(-4))
    complete(clients["maya"], a, day(-2))                                   # 2 days
    b = create_activity(clients["ravi"], "Ravi Done B", start_date=day(-3))
    complete(clients["maya"], b, day(-3))                                   # same day
    create_activity(clients["ravi"], "Ravi Open", follow_up_date=day(-1), start_date=day(-2))
    c = create_activity(clients["riya"], "Riya Done", start_date=day(-6))
    complete(clients["maya"], c, day(0))                                    # 6 days
    create_activity(clients["rohan"], "Rohan Open", follow_up_date=day(0))


def test_overview_numbers_and_time_to_complete(clients):
    seed_data(clients)
    ov = clients["ravi"].get("/api/stats/overview").json()
    assert (ov["total"], ov["completed"], ov["pending"], ov["completion_rate"]) == (3, 2, 1, 67)
    assert ov["durations"] == {"avg_days_to_complete": 1.0, "fastest_days": 0, "slowest_days": 2, "timed_count": 2}
    assert ov["follow_ups"]["overdue"] == 1
    assert ov["scope_label"] == "Your activities" and len(ov["last_7_days"]) == 7


def test_overview_is_scoped_by_role(clients):
    seed_data(clients)
    total = lambda key: clients[key].get("/api/stats/overview").json()["total"]  # noqa: E731
    assert total("ravi") == 3 and total("riya") == 1
    assert total("maya") == 4          # Ravi + Riya
    assert total("mohan") == 1 and total("admin") == 5
    assert clients["admin"].get("/api/stats/overview").json()["scope_label"] == "Whole company"
    assert clients["maya"].get("/api/stats/overview").json()["scope_label"] == "Your team"


def test_overview_period_uses_start_date_and_owner_filter_is_checked(clients, people):
    seed_data(clients)
    assert clients["admin"].get("/api/stats/overview", params={"period": "today"}).json()["total"] == 1
    r = clients["admin"].get("/api/stats/overview", params={"owner_id": str(people["riya"].id)}).json()
    assert r["total"] == 1 and r["scope_label"] == "Riya Rep"
    assert clients["maya"].get("/api/stats/overview", params={"owner_id": str(people["rohan"].id)}).status_code == 404


def test_team_endpoint_roles_and_content(clients):
    seed_data(clients)
    assert clients["ravi"].get("/api/stats/team").status_code == 403
    rows = clients["maya"].get("/api/stats/team").json()
    assert sorted(r["full_name"] for r in rows) == ["Maya Manager", "Ravi Rep", "Riya Rep"]
    ravi = next(r for r in rows if r["full_name"] == "Ravi Rep")
    assert (ravi["total"], ravi["completed"], ravi["completion_rate"], ravi["avg_days_to_complete"]) == (3, 2, 67, 1.0)
    assert ravi["follow_ups_overdue"] == 1 and ravi["manager_name"] == "Maya Manager"
    everyone = clients["admin"].get("/api/stats/team").json()
    assert len(everyone) == 5 and all(r["role"] != "admin" for r in everyone)      # 2 managers + 3 reps
    assert everyone[0]["full_name"] == "Ravi Rep"                                   # most completed first


# ------------------------------------------------------------------- reports
def test_report_summary_scope_and_filters(clients, people):
    seed_data(clients)
    body = clients["maya"].get("/api/reports/summary", params={"status": "completed"}).json()
    assert body["overview"]["total"] == 3 and body["filters"]["Status"] == "Completed"
    assert {r["full_name"] for r in body["by_employee"]} == {"Maya Manager", "Ravi Rep", "Riya Rep"}
    mine = clients["ravi"].get("/api/reports/summary").json()
    assert mine["by_employee"] == [] and mine["overview"]["total"] == 3


def test_csv_export_respects_scope_and_is_excel_friendly(clients):
    seed_data(clients)
    response = clients["ravi"].get("/api/reports/activities.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    assert response.content.startswith(b"\xef\xbb\xbf")                           # UTF-8 BOM
    text = response.content.decode("utf-8-sig")
    assert "Ravi Done A" in text and "Riya Done" not in text and "Rohan Open" not in text
    assert text.splitlines()[0].startswith("Start date,Salesperson,Customer")
    admin_text = clients["admin"].get("/api/reports/activities.csv", params={"status": "completed"}).content.decode("utf-8-sig")
    assert "Riya Done" in admin_text and "Ravi Open" not in admin_text


def test_csv_formula_injection_is_neutralised(clients):
    create_activity(clients["ravi"], "=HYPERLINK(\"http://evil\")")
    text = clients["ravi"].get("/api/reports/activities.csv").content.decode("utf-8-sig")
    assert "'=HYPERLINK" in text
    assert csv_safe("+1") == "'+1" and csv_safe("@x") == "'@x" and csv_safe("normal") == "normal" and csv_safe(None) == ""


def test_pdf_export(clients):
    seed_data(clients)
    for key in ("ravi", "maya", "admin"):
        response = clients[key].get("/api/reports/activities.pdf")
        assert response.status_code == 200 and response.headers["content-type"] == "application/pdf"
        assert response.content.startswith(b"%PDF") and len(response.content) > 1500
    empty = clients["rohan"].get("/api/reports/activities.pdf", params={"search": "zzz"})
    assert empty.status_code == 200


def test_exports_need_login_and_are_rate_limited(clients, monkeypatch):
    anon = TestClient(app)
    assert anon.get("/api/reports/activities.csv").status_code == 401
    assert anon.get("/api/reports/activities.pdf").status_code == 401
    from app.config import settings
    monkeypatch.setattr(settings, "export_rate_limit", 2)
    codes = [clients["ravi"].get("/api/reports/activities.csv").status_code for _ in range(4)]
    assert codes == [200, 200, 429, 429]


def test_health_and_security_headers(clients):
    client = TestClient(app)
    health = client.get("/api/health")
    assert health.status_code == 200 and health.json() == {"status": "ok", "database": "ok"}
    headers = client.get("/").headers
    assert headers["x-content-type-options"] == "nosniff" and headers["x-frame-options"] == "DENY"
    assert "script-src 'self'" in headers["content-security-policy"]
    assert client.get("/api/auth/config").headers["cache-control"] == "no-store"
    assert "content-security-policy" not in client.get("/docs").headers      # Swagger needs its own scripts


def test_unexpected_errors_return_a_safe_500(clients, monkeypatch):
    from app.crud import stats as stats_crud

    def boom(*_args, **_kwargs):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(stats_crud, "overview", boom)
    quiet = TestClient(app, raise_server_exceptions=False)
    quiet.cookies.update(clients["ravi"].cookies)
    response = quiet.get("/api/stats/overview")
    assert response.status_code == 500
    assert response.json() == {"detail": "Something went wrong on our side. Please try again."}
    assert "secret" not in response.text
