import pytest

from app.ai import gateway
from app.database.sql_models import (
    AIUsageLog, Application, AuditLog, Company, Job, JobRequirement, ProbationOutcome, RequirementResult,
)
from app.insights import reality_check, simulator
from tests.helpers_board import make_world


@pytest.mark.parametrize("hired_total,with_req,expected", [
    (9, 0, "not_enough_data"), (10, 2, "consider_nice_to_have"), (10, 3, "review"),
    (10, 7, "review"), (10, 8, "keep"), (20, 5, "consider_nice_to_have"), (20, 6, "review"),
])
def test_rule_boundaries(hired_total, with_req, expected):
    assert reality_check.suggestion_for(hired_total, with_req) == expected


def test_rule_boundaries_follow_the_thresholds_given():
    assert reality_check.suggestion_for(5, 4, low_pct=50, high_pct=90, min_hired=5) == "review"
    assert reality_check.suggestion_for(5, 5, low_pct=50, high_pct=90, min_hired=5) == "keep"
    assert reality_check.suggestion_for(5, 2, low_pct=50, high_pct=90, min_hired=5) == "consider_nice_to_have"
    assert reality_check.suggestion_for(4, 4, low_pct=50, high_pct=90, min_hired=5) == "not_enough_data"


# A hand-computed fixture. Twelve real applications; the first ten were hired.
#   R1 (must-have):  CV met for 0-7, not_found for 8-11; interview evidence for 8.
#   R2 (must-have):  CV met for 0-2, partial for the rest; interview evidence for 3, partial for 4.
#   R3 (nice-to-have) and R4 (inactive must-have) are never listed.
#   Probation: 0 failed, 1 extended, 2-9 passed.


def build(db, company, job, simulated=False, count=12, hires=10, prefix="#A"):
    apps = []
    for i in range(count):
        row = Application(company_id=company.id, job_id=job.id, alias=f"{prefix}{i}", stage="ready_for_hr",
                          cv_status="meets", is_simulated=simulated,
                          final_outcome="hired" if i < hires else "not_hired")
        db.add(row)
        apps.append(row)
    db.commit()
    return apps


def add_result(db, application, requirement, source, status):
    db.add(RequirementResult(application_id=application.id, requirement_id=requirement.id, source=source,
                             status=status))


@pytest.fixture
def world(db):
    return make_world(db)


@pytest.fixture
def company(world):
    return world["company"]


@pytest.fixture
def job(db, world):
    job = world["job"]
    for row in db.query(JobRequirement).filter_by(job_id=job.id):
        db.delete(row)
    db.commit()
    r1 = JobRequirement(company_id=job.company_id, job_id=job.id, text="Python", must_have=True, position=0)
    r2 = JobRequirement(company_id=job.company_id, job_id=job.id, text="Team leading", must_have=True, position=1)
    r3 = JobRequirement(company_id=job.company_id, job_id=job.id, text="Kubernetes", must_have=False, position=2)
    r4 = JobRequirement(company_id=job.company_id, job_id=job.id, text="Retired", must_have=True, position=3,
                        active=False)
    db.add_all([r1, r2, r3, r4])
    db.commit()
    job.reqs = (r1, r2, r3, r4)
    return job


@pytest.fixture
def fixture(db, company, job):
    r1, r2, r3, r4 = job.reqs
    apps = build(db, company, job)
    for i, row in enumerate(apps):
        add_result(db, row, r1, "cv", "met" if i < 8 else "not_found")
        add_result(db, row, r2, "cv", "met" if i < 3 else "partial")
        add_result(db, row, r3, "cv", "not_found")
        add_result(db, row, r4, "cv", "not_found")
    add_result(db, apps[8], r1, "interview", "evidence")
    add_result(db, apps[3], r2, "interview", "evidence")
    add_result(db, apps[4], r2, "interview", "partial")
    results = {0: "failed", 1: "extended", **{i: "passed" for i in range(2, 10)}}
    for i, result in results.items():
        db.add(ProbationOutcome(company_id=company.id, application_id=apps[i].id, result=result))
    db.commit()
    return apps


def correct(db, application, to="meets"):
    db.add(AuditLog(company_id=application.company_id, action="cv_status_corrected", target_type="application",
                    target_id=application.id, payload={"from": "not_met" if to == "meets" else "meets", "to": to,
                                                       "reason": "x"}))
    db.commit()


def by_text(rows):
    return {row.text: row for row in rows}


def test_metrics_match_a_hand_computed_fixture(db, company, job, fixture):
    rows = reality_check.report(db, company.id, job.id, simulated=False)
    assert [row.text for row in rows] == ["Python", "Team leading"]
    python, lead = rows
    assert python.requirement_id == job.reqs[0].id
    assert python.cv_miss_rate == pytest.approx(4 / 12, abs=1e-4)
    assert (python.hired_total, python.hired_with_requirement) == (10, 9)
    assert python.probation_passed_without_requirement == 1  # application 9 passed and never showed Python
    assert python.suggestion == "keep"
    assert lead.cv_miss_rate == pytest.approx(9 / 12, abs=1e-4)
    assert (lead.hired_total, lead.hired_with_requirement) == (10, 4)  # CV met 0-2, interview evidence 3; partial no
    assert lead.probation_passed_without_requirement == 6  # passed 2..9 minus 2 and 3
    assert lead.suggestion == "review"


def test_only_active_must_haves_are_listed(db, company, job, fixture):
    rows = reality_check.report(db, company.id, job.id, simulated=False)
    assert {row.requirement_id for row in rows} == {job.reqs[0].id, job.reqs[1].id}


def test_hired_with_requirement_counts_cv_met_or_interview_evidence_only(db, company, job):
    r1 = job.reqs[0]
    apps = build(db, company, job, count=4, hires=4)
    add_result(db, apps[0], r1, "cv", "met")
    add_result(db, apps[1], r1, "interview", "evidence")
    add_result(db, apps[2], r1, "cv", "partial")
    add_result(db, apps[2], r1, "interview", "partial")
    add_result(db, apps[3], r1, "cv", "not_found")
    db.commit()
    row = by_text(reality_check.report(db, company.id, job.id, simulated=False))["Python"]
    assert (row.hired_total, row.hired_with_requirement) == (4, 2)


def test_a_requirement_with_no_cv_results_has_no_miss_rate_and_no_error(db, company, job):
    rows = reality_check.report(db, company.id, job.id, simulated=False)
    assert [row.cv_miss_rate for row in rows] == [None, None]
    assert {row.suggestion for row in rows} == {"not_enough_data"}
    assert {row.hired_total for row in rows} == {0}


def test_hr_label_corrections_count_audit_rows_for_this_job_and_requirement(db, company, job, fixture):
    correct(db, fixture[8])
    correct(db, fixture[10])
    correct(db, fixture[1], to="not_met")  # the other direction says nothing about a criterion being too strict
    other = Job(company_id=company.id, title="Other", slug="other-job", status="published", version=1,
                interview_languages=[])
    db.add(other)
    db.commit()
    elsewhere = build(db, company, other, count=1, hires=0, prefix="#O")[0]
    correct(db, elsewhere)
    rows = by_text(reality_check.report(db, company.id, job.id, simulated=False))
    assert rows["Python"].hr_label_corrections == 2   # 8 and 10 were not_found on Python
    assert rows["Team leading"].hr_label_corrections == 2
    assert rows["Python"].too_strict_signal is False


def test_three_corrections_raise_the_too_strict_signal_on_the_requirements_that_were_missed(db, company, job, fixture):
    for index in (8, 9, 10):
        correct(db, fixture[index])
    rows = by_text(reality_check.report(db, company.id, job.id, simulated=False))
    assert rows["Python"].hr_label_corrections == 3
    assert rows["Python"].too_strict_signal is True
    assert rows["Team leading"].too_strict_signal is True


def test_a_correction_on_an_application_that_met_the_requirement_does_not_count_against_it(db, company, job, fixture):
    for index in (0, 1, 2):  # all met Python on the CV
        correct(db, fixture[index])
    rows = by_text(reality_check.report(db, company.id, job.id, simulated=False))
    assert rows["Python"].hr_label_corrections == 0
    assert rows["Python"].too_strict_signal is False


def test_thresholds_are_read_from_the_company(db, company, job, fixture):
    before = by_text(reality_check.report(db, company.id, job.id, simulated=False))
    assert before["Team leading"].suggestion == "review"  # 40%
    company.reality_low_pct = 50
    db.commit()
    assert by_text(reality_check.report(db, company.id, job.id, simulated=False))["Team leading"].suggestion \
        == "consider_nice_to_have"
    company.reality_low_pct, company.reality_high_pct = 30, 35
    db.commit()
    assert by_text(reality_check.report(db, company.id, job.id, simulated=False))["Team leading"].suggestion == "keep"
    company.reality_min_hired = 11
    db.commit()
    assert {r.suggestion for r in reality_check.report(db, company.id, job.id, simulated=False)} == {"not_enough_data"}


def test_new_companies_start_with_the_documented_thresholds(db, company):
    db.refresh(company)
    assert (company.reality_low_pct, company.reality_high_pct, company.reality_min_hired) == (30, 70, 10)


def test_real_and_simulated_applications_never_mix(db, company, job, fixture):
    r1 = job.reqs[0]
    sims = build(db, company, job, simulated=True, count=3, hires=3, prefix="#S")
    for row in sims:
        add_result(db, row, r1, "cv", "not_found")
    db.commit()
    real = by_text(reality_check.report(db, company.id, job.id, simulated=False))["Python"]
    simulated = by_text(reality_check.report(db, company.id, job.id, simulated=True))["Python"]
    assert (real.hired_total, real.hired_with_requirement) == (10, 9)
    assert simulated.hired_total == 3 and simulated.hired_with_requirement == 0
    assert simulated.cv_miss_rate == 1.0
    assert simulated.probation_passed_without_requirement == 0


def test_the_report_makes_no_ai_call_and_changes_nothing(db, company, job, fixture, monkeypatch):
    calls = []
    for name in ("generate_text", "generate_structured", "embed"):
        monkeypatch.setattr(gateway, name, lambda *args, _name=name, **kwargs: calls.append(_name))

    def snapshot():
        reqs = [(r.id, r.text, r.must_have, r.visibility, r.active, r.position)
                for r in db.query(JobRequirement).order_by(JobRequirement.id)]
        return reqs, db.get(Job, job.id).version, db.query(AuditLog).count()

    db.expire_all()
    before = snapshot()
    reality_check.report(db, company.id, job.id, simulated=False)
    reality_check.report(db, company.id, job.id, simulated=True)
    db.rollback()
    assert calls == []
    assert db.query(AIUsageLog).count() == 0
    assert snapshot() == before


def test_a_suggestion_carries_an_action_that_points_to_jd_studio_and_does_nothing_itself(db, company, job, fixture):
    rows = by_text(reality_check.report(db, company.id, job.id, simulated=False))
    action = rows["Team leading"].action
    assert action["type"] == "open_jd_studio"
    assert action["job_id"] == job.id and action["requirement_id"] == job.reqs[1].id
    assert rows["Python"].action is None  # keep: nothing to suggest
    assert set(action) == {"type", "job_id", "requirement_id"}


# The route


def url(world, path="reality-check", **query):
    suffix = "?" + "&".join(f"{k}={v}" for k, v in query.items()) if query else ""
    return f"/api/companies/{world['company'].id}/jobs/{world['job'].id}/{path}{suffix}"


def test_the_route_is_hr_only_and_scoped_to_the_company(client, world, job):
    people = world["people"]
    assert client.get(url(world)).status_code in (401, 403)
    assert client.get(url(world), headers=people["emp"]["headers"]).status_code == 403
    assert client.get(url(world), headers=people["hr2"]["headers"]).status_code == 403
    assert client.get(url(world), headers=people["hr"]["headers"]).status_code == 200
    gone = f"/api/companies/{world['company'].id}/jobs/{world['other_job'].id}/reality-check"
    assert client.get(gone, headers=people["hr"]["headers"]).status_code == 404


def test_the_route_returns_rows_thresholds_and_the_banner_only_for_simulated(client, db, world, job, fixture):
    headers = world["people"]["hr"]["headers"]
    real = client.get(url(world), headers=headers).json()
    assert real["simulated"] is False and real["banner"] is None
    assert real["thresholds"] == {"low_pct": 30, "high_pct": 70, "min_hired": 10}
    assert [row["text"] for row in real["rows"]] == ["Python", "Team leading"]
    assert set(real["rows"][1]) == {
        "requirement_id", "text", "cv_miss_rate", "hired_total", "hired_with_requirement", "hr_label_corrections",
        "probation_passed_without_requirement", "suggestion", "too_strict_signal", "action",
    }
    sim = client.get(url(world, data="simulated"), headers=headers).json()
    assert sim["simulated"] is True and sim["banner"] == "Simulated data"
    assert all(row["hired_total"] == 0 for row in sim["rows"])
    assert client.get(url(world, data="all"), headers=headers).status_code == 422


def test_the_default_view_is_real_data(client, world, job, fixture):
    body = client.get(url(world), headers=world["people"]["hr"]["headers"]).json()
    assert body["rows"][0]["hired_total"] == 10


def test_the_simulated_demo_tells_the_story_on_seed_42(db):
    company = Company(slug="sori-labs", name="Sori", is_sample=True)
    db.add(company)
    db.commit()
    job = Job(company_id=company.id, title="Backend", slug="sori-backend", status="published", version=1,
              interview_languages=[])
    db.add(job)
    db.commit()
    for i, text in enumerate(["A", "B", "C", "D"]):
        db.add(JobRequirement(company_id=company.id, job_id=job.id, text=text, must_have=True, position=i))
    db.commit()
    simulator.simulate(db, company, seed=42)
    rows = reality_check.report(db, company.id, job.id, simulated=True)
    assert rows[0].suggestion == "keep" and rows[0].cv_miss_rate >= 0.5
    assert rows[-1].suggestion == "consider_nice_to_have"
    assert rows[-1].probation_passed_without_requirement >= 5
    assert all(row.hr_label_corrections == 0 and row.too_strict_signal is False for row in rows)
    assert reality_check.report(db, company.id, job.id, simulated=False)[0].hired_total == 0
