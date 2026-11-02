import json

import pytest
from fastapi.testclient import TestClient

from app.ai import gateway
from app.ai.providers import fake
from app.database.models_insights import SIMULATED_COST_SOURCE
from app.database.sql_models import Application, ChannelCost, InterviewScorecard, VoiceSession
from app.insights import channels, commentary
from app.main import create_app
from tests.helpers_board import make_world


@pytest.fixture
def world(db):
    return make_world(db)


@pytest.fixture
def api():
    return TestClient(create_app())


_counter = {"n": 0}


def add(db, world, channel, stage="ready_for_hr", cv="meets", band=None, decision="pending", session=False,
        scorecard=False, outcome=None, fast=False, simulated=False, job=None):
    job = job or world["job"]
    _counter["n"] += 1
    row = Application(
        company_id=job.company_id, job_id=job.id, job_version=1, alias=f"#T{_counter['n']}", source_channel=channel,
        stage=stage, cv_status=cv, interview_band=band, hr_decision=decision, fast_tracked=fast,
        final_outcome=outcome, is_simulated=simulated,
    )
    db.add(row)
    db.commit()
    if session:
        db.add(VoiceSession(company_id=job.company_id, purpose="screening", application_id=row.id, language="en",
                            status="completed"))
    if scorecard:
        db.add(InterviewScorecard(company_id=job.company_id, application_id=row.id, recommendation="hire"))
    db.commit()
    return row


def cost(db, world, channel, month, amount, source="manual", job=None):
    job = job or world["job"]
    db.add(ChannelCost(company_id=job.company_id, job_id=job.id, channel=channel, period_month=month,
                       amount_vnd=amount, source=source))
    db.commit()


def fixture_rows(db, world):
    """linkedin: 6 applications. referral: 2. topcv: 1 with a cost and no approval."""
    add(db, world, "linkedin", cv="meets", band="many", decision="approved", session=True, scorecard=True,
        outcome="hired")
    add(db, world, "linkedin", cv="not_met", band="many", decision="approved", session=True)  # hidden gem
    add(db, world, "linkedin", stage="withdrawn", cv="meets")
    add(db, world, "linkedin", stage="ready_for_hr", cv="meets", fast=True)  # declined recording, fast tracked
    add(db, world, "linkedin", stage="declined_recording", cv="meets")
    add(db, world, "linkedin", cv="not_met", band="few", decision="rejected", session=True)
    add(db, world, "referral", cv="meets", band="few", decision="approved", session=True)
    add(db, world, "referral", stage="submitted", cv=None)
    add(db, world, "topcv", stage="invited", cv="meets")
    cost(db, world, "linkedin", "2026-08", 1_000_000)
    cost(db, world, "linkedin", "2026-09", 500_000)
    cost(db, world, "topcv", "2026-09", 200_000)


def rows_by_channel(table):
    return {row.channel: row for row in table.rows}


def test_table_matches_hand_computed_values(db, world):
    fixture_rows(db, world)
    add(db, world, "linkedin", job=world["other_job"], decision="approved")  # another job: not counted
    rows = rows_by_channel(channels.channel_table(db, world["company"].id, world["job"].id, simulated=False))
    assert set(rows) == {"linkedin", "referral", "topcv"}
    linkedin = rows["linkedin"]
    assert (linkedin.applications, linkedin.cv_meets, linkedin.sessions_completed) == (6, 4, 3)
    assert linkedin.completion_rate == pytest.approx(0.5)
    assert (linkedin.hr_approved, linkedin.hidden_gems, linkedin.interviews, linkedin.hires) == (2, 1, 1, 1)
    assert linkedin.approval_rate == pytest.approx(2 / 6, abs=1e-4)
    assert linkedin.cost == 1_500_000
    assert linkedin.cost_per_approved == 750_000
    referral = rows["referral"]
    assert (referral.applications, referral.cv_meets, referral.sessions_completed) == (2, 1, 1)
    assert (referral.hr_approved, referral.hidden_gems, referral.interviews, referral.hires) == (1, 0, 0, 0)
    assert referral.approval_rate == pytest.approx(0.5)


def test_zero_applications_gives_none_rates_not_an_exception(db, world):
    cost(db, world, "facebook", "2026-09", 300_000)
    row = rows_by_channel(channels.channel_table(db, world["company"].id, world["job"].id, simulated=False))["facebook"]
    assert row.applications == 0
    assert row.completion_rate is None and row.approval_rate is None
    assert row.cost == 300_000 and row.cost_per_approved is None


def test_cost_is_none_when_not_entered_and_cost_per_approved_needs_both(db, world):
    fixture_rows(db, world)
    rows = rows_by_channel(channels.channel_table(db, world["company"].id, world["job"].id, simulated=False))
    assert rows["referral"].cost is None and rows["referral"].cost_per_approved is None  # approved but no cost
    assert rows["topcv"].cost == 200_000 and rows["topcv"].cost_per_approved is None  # cost but nobody approved
    assert rows["topcv"].hr_approved == 0


def test_real_and_simulated_never_mix(db, world):
    fixture_rows(db, world)
    add(db, world, "linkedin", decision="approved", simulated=True)
    add(db, world, "tiktok", decision="approved", simulated=True)
    cost(db, world, "linkedin", "2026-10", 9_000_000, source=SIMULATED_COST_SOURCE)
    company_id, job_id = world["company"].id, world["job"].id
    real = rows_by_channel(channels.channel_table(db, company_id, job_id, simulated=False))
    assert real["linkedin"].applications == 6 and real["linkedin"].cost == 1_500_000 and "tiktok" not in real
    simulated = rows_by_channel(channels.channel_table(db, company_id, job_id, simulated=True))
    assert set(simulated) == {"linkedin", "tiktok"}
    assert simulated["linkedin"].applications == 1 and simulated["linkedin"].cost == 9_000_000


def test_api_default_is_real_when_real_rows_exist_else_simulated(db, world, api):
    url = f"/api/companies/{world['company'].id}/jobs/{world['job'].id}/channels"
    hr = world["people"]["hr"]["headers"]
    add(db, world, "linkedin", simulated=True)
    body = api.get(url, headers=hr).json()
    assert body["simulated"] is True and body["has_simulated"] is True and body["has_real"] is False
    add(db, world, "referral")
    body = api.get(url, headers=hr).json()
    assert body["simulated"] is False and body["has_real"] and body["has_simulated"]
    assert [row["channel"] for row in body["table"]["rows"]] == ["referral"]
    body = api.get(url + "?data=simulated", headers=hr).json()
    assert body["simulated"] is True
    assert [row["channel"] for row in body["table"]["rows"]] == ["linkedin"]
    assert api.get(url + "?data=both", headers=hr).status_code == 422


def test_talent_pool_is_its_own_channel(db, world):
    add(db, world, "talent_pool", decision="approved", session=True)
    add(db, world, "linkedin")
    rows = rows_by_channel(channels.channel_table(db, world["company"].id, world["job"].id, simulated=False))
    assert rows["talent_pool"].applications == 1 and rows["talent_pool"].hr_approved == 1
    assert rows["linkedin"].applications == 1


def test_missing_channel_is_grouped_as_direct(db, world):
    add(db, world, None)
    rows = rows_by_channel(channels.channel_table(db, world["company"].id, world["job"].id, simulated=False))
    assert rows["direct"].applications == 1


# ---- numbers in commentary

def table_with(**row):
    base = dict(channel="linkedin", applications=24, cv_meets=10, sessions_completed=8, completion_rate=1 / 3,
                hr_approved=10, approval_rate=0.41666, hidden_gems=1, interviews=5, hires=3, cost=1_500_000,
                cost_per_approved=150_000, small_sample=True)
    base.update(row)
    return channels.ChannelTable(rows=[channels.ChannelRow(**base)])


def test_numbers_in_extracts_and_normalises():
    assert commentary.numbers_in("41.7% and 3 hires, about 40") == {"41.7", "3", "40"}
    assert commentary.numbers_in("cost 1,500,000 VND, 12 apps") == {"1500000", "12"}
    assert commentary.numbers_in("no digits here") == set()
    assert commentary.numbers_in("rate 41,7%") == {"41.7"}


def test_check_numbers_accepts_table_values_at_shown_precision():
    table = table_with()
    assert commentary.check_numbers("LinkedIn has 24 applications and a 41.7% approval rate.", table)
    assert commentary.check_numbers("Cost per approved is 150,000 VND, 33.3% completion.", table)
    assert commentary.check_numbers("Referral is worth a look.", table)  # no numbers at all


@pytest.mark.parametrize("text", [
    "About 40% approval.", "Approval is 42%.", "Approval is 41.67%.", "There were 25 applications.",
    "Moving 20 applications.",
])
def test_check_numbers_rejects_values_not_in_the_table(text):
    assert not commentary.check_numbers(text, table_with())


def explain_with(responses, table=None):
    for observations in responses:
        fake.enqueue("channel_commentary", json.dumps({"observations": observations}, ensure_ascii=False))
    return commentary.explain(table or table_with(), "en", None)


def test_explain_returns_observations_when_numbers_are_in_the_table():
    result = explain_with([["LinkedIn: 24 applications, 41.7% approved."]])
    assert result.observations == ["LinkedIn: 24 applications, 41.7% approved."]


def test_explain_sends_only_the_table_and_the_language():
    explain_with([["ok"]])
    prompt = fake.last_messages()[-1]["content"]
    assert "<table>" in prompt and "</table>" in prompt and '"channel": "linkedin"' in prompt


def test_explain_retries_once_then_gives_up(monkeypatch):
    calls = []
    original = gateway.generate_structured

    def spy(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(gateway, "generate_structured", spy)
    assert explain_with([["About 40%."], ["Still 40%."], ["41.7%"]]) is None
    assert len(calls) == 2


def test_explain_accepts_a_good_second_attempt():
    result = explain_with([["About 40%."], ["41.7% approved."]])
    assert result.observations == ["41.7% approved."]


def test_explain_returns_none_when_the_ai_fails():
    fake.enqueue("channel_commentary", "not json")
    fake.enqueue("channel_commentary", "not json")
    assert commentary.explain(table_with(), "en", None) is None


# ---- API

def get_channels(api, world, query=""):
    url = f"/api/companies/{world['company'].id}/jobs/{world['job'].id}/channels{query}"
    return api.get(url, headers=world["people"]["hr"]["headers"])


def test_small_sample_statement_is_added_by_code_whatever_the_ai_says(db, world, api):
    fixture_rows(db, world)  # every channel is under 30 applications
    fake.enqueue("channel_commentary", json.dumps({"observations": ["All fine, large sample."]}))
    body = get_channels(api, world).json()
    assert body["small_sample_note"] == "Sample too small, treat as a hint"
    assert all(row["small_sample"] for row in body["table"]["rows"])
    assert body["commentary"]["observations"] == ["All fine, large sample."]


def test_no_small_sample_note_at_30_applications(db, world, api):
    for _ in range(30):
        add(db, world, "linkedin")
    body = get_channels(api, world).json()
    assert body["small_sample_note"] is None
    assert body["table"]["rows"][0]["small_sample"] is False


def test_small_sample_note_in_vietnamese(db, world, api):
    add(db, world, "linkedin")
    body = get_channels(api, world, "?language=vi").json()
    assert body["small_sample_note"] and body["small_sample_note"] != "Sample too small, treat as a hint"


def test_ai_failure_returns_the_table_without_commentary(db, world, api):
    fixture_rows(db, world)
    fake.enqueue("channel_commentary", "garbage")
    fake.enqueue("channel_commentary", "garbage")
    response = get_channels(api, world)
    assert response.status_code == 200
    body = response.json()
    assert body["commentary"] is None and len(body["table"]["rows"]) == 3


def test_invented_numbers_twice_returns_the_table_without_commentary(db, world, api):
    fixture_rows(db, world)
    for _ in range(2):
        fake.enqueue("channel_commentary", json.dumps({"observations": ["LinkedIn approves about 40%."]}))
    body = get_channels(api, world).json()
    assert body["commentary"] is None and body["table"]["rows"]


def test_demo_responder_cites_applications_and_approval_rate(db, world, api):
    fixture_rows(db, world)
    body = get_channels(api, world).json()
    lines = body["commentary"]["observations"]
    assert len(lines) == 3 and all(line.startswith("[Demo AI]") for line in lines)
    assert any("33.3%" in line and "6" in line for line in lines)


def test_empty_job_makes_no_ai_call(db, world, api):
    body = get_channels(api, world).json()
    assert body["table"]["rows"] == [] and body["commentary"] is None and body["small_sample_note"] is None


def test_not_entered_cost_shows_as_null_and_unknown_job_is_404(db, world, api):
    add(db, world, "linkedin", decision="approved")
    body = get_channels(api, world).json()
    row = body["table"]["rows"][0]
    assert row["cost"] is None and row["cost_per_approved"] is None
    url = f"/api/companies/{world['company'].id}/jobs/{world['other_job'].id}/channels"
    assert api.get(url, headers=world["people"]["hr"]["headers"]).status_code == 404


# ---- costs

def costs_url(world):
    return f"/api/companies/{world['company'].id}/channel-costs"


def post_costs(api, world, items, job_id=None):
    body = {"job_id": job_id or world["job"].id, "items": items}
    return api.post(costs_url(world), json=body, headers=world["people"]["hr"]["headers"])


def test_json_costs_upsert(db, world, api):
    item = {"channel": "LinkedIn", "period_month": "2026-09", "amount_vnd": 1_000_000}
    assert post_costs(api, world, [item]).json() == {"saved": 1}
    assert post_costs(api, world, [{**item, "amount_vnd": 2_000_000}]).status_code == 200
    rows = db.query(ChannelCost).all()
    assert len(rows) == 1 and rows[0].amount_vnd == 2_000_000 and rows[0].channel == "linkedin"
    assert rows[0].source == "manual" and rows[0].job_id == world["job"].id


def test_manual_cost_overwrites_a_simulated_one_and_sets_the_real_source(db, world, api):
    cost(db, world, "linkedin", "2026-09", 5, source=SIMULATED_COST_SOURCE)
    post_costs(api, world, [{"channel": "linkedin", "period_month": "2026-09", "amount_vnd": 7}])
    db.expire_all()
    rows = db.query(ChannelCost).all()
    assert [(r.amount_vnd, r.source) for r in rows] == [(7, "manual")]


@pytest.mark.parametrize("item", [
    {"channel": "linkedin", "period_month": "2026-09", "amount_vnd": -1},
    {"channel": "linkedin", "period_month": "2026-9", "amount_vnd": 1},
    {"channel": "linkedin", "period_month": "2026-13", "amount_vnd": 1},
    {"channel": "", "period_month": "2026-09", "amount_vnd": 1},
    {"channel": "x" * 51, "period_month": "2026-09", "amount_vnd": 1},
])
def test_bad_cost_items_get_422(db, world, api, item):
    assert post_costs(api, world, [item]).status_code == 422
    assert db.query(ChannelCost).count() == 0


def test_costs_for_a_job_of_another_company_get_404(db, world, api):
    item = {"channel": "linkedin", "period_month": "2026-09", "amount_vnd": 1}
    assert post_costs(api, world, [item], job_id=world["other_job"].id).status_code == 404


def post_csv(api, world, text, job_id=None):
    return api.post(costs_url(world), data={"job_id": str(job_id or world["job"].id)},
                    files={"file": ("costs.csv", text.encode(), "text/csv")},
                    headers=world["people"]["hr"]["headers"])


def test_csv_costs_are_imported(db, world, api):
    response = post_csv(api, world, "channel,period_month,amount_vnd\nlinkedin,2026-08,1000000\nfacebook,2026-09,0\n")
    assert response.status_code == 200 and response.json() == {"saved": 2}
    assert {row.source for row in db.query(ChannelCost)} == {"csv"}


def test_csv_with_bad_rows_reports_lines_and_saves_nothing(db, world, api):
    text = ("channel,period_month,amount_vnd\nlinkedin,2026-08,1000\nlinkedin,2026-8,1000\nfacebook,2026-09,-5\n"
            "topcv,2026-09,abc\n")
    response = post_csv(api, world, text)
    assert response.status_code == 422
    assert [error["line"] for error in response.json()["detail"]] == [3, 4, 5]
    assert db.query(ChannelCost).count() == 0


def test_csv_with_wrong_header_is_rejected(db, world, api):
    assert post_csv(api, world, "name,month\na,b\n").status_code == 422
    assert db.query(ChannelCost).count() == 0


def test_costs_feed_the_table(db, world, api):
    add(db, world, "linkedin", decision="approved")
    post_costs(api, world, [{"channel": "linkedin", "period_month": "2026-09", "amount_vnd": 400_000}])
    row = get_channels(api, world).json()["table"]["rows"][0]
    assert row["cost"] == 400_000 and row["cost_per_approved"] == 400_000


# ---- access

def test_non_hr_and_other_company_hr_get_403(db, world, api):
    employee = world["people"]["emp"]["headers"]
    foreign = world["people"]["hr2"]["headers"]
    for headers in (employee, foreign):
        assert api.get(f"/api/companies/{world['company'].id}/jobs/{world['job'].id}/channels",
                       headers=headers).status_code == 403
        assert api.post(costs_url(world), json={"job_id": world["job"].id, "items": []},
                        headers=headers).status_code == 403
    assert api.get(f"/api/companies/{world['company'].id}/jobs/{world['job'].id}/channels").status_code in (401, 403)
