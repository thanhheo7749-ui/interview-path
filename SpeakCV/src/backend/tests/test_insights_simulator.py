from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.ai import gateway
from app.cli import main
from app.database import models_insights
from app.database.database import Base, engine
from app.database.sql_models import (
    AIUsageLog, Application, AuditLog, ChannelCost, Company, CompanyMember, InterviewScorecard, Job, JobRequirement,
    ProbationOutcome, RequirementResult, VoiceSession,
)
from app.hiring import analysis, applications, board, cv_processing, retention
from app.insights import simulator
from app.main import create_app
from tests.helpers import auth_header, make_user

SLUG = "sample-co"


def make_job(db, company, title="Backend", status="published"):
    job = Job(company_id=company.id, title=title, slug=f"{company.slug}-{title.lower()}", status=status, version=3,
              interview_languages=["vi", "en"])
    db.add(job)
    db.commit()
    db.add_all([
        JobRequirement(company_id=company.id, job_id=job.id, text="Python", must_have=True, position=0),
        JobRequirement(company_id=company.id, job_id=job.id, text="Team leading", must_have=True, position=1),
        JobRequirement(company_id=company.id, job_id=job.id, text="University degree", must_have=True, position=2),
        JobRequirement(company_id=company.id, job_id=job.id, text="Kubernetes", must_have=False, position=3),
        JobRequirement(company_id=company.id, job_id=job.id, text="Retired", must_have=True, position=4, active=False),
    ])
    db.commit()
    return job


@pytest.fixture
def company(db):
    row = Company(slug=SLUG, name="Sample Co", is_sample=True)
    db.add(row)
    db.commit()
    return row


@pytest.fixture
def job(db, company):
    return make_job(db, company)


def simulated_rows(db, company_id):
    return db.query(Application).filter_by(company_id=company_id, is_simulated=True).order_by(Application.alias).all()


def snapshot(db, company_id):
    """Everything the simulator wrote for the company, with database IDs replaced by aliases."""
    rows = simulated_rows(db, company_id)
    alias_of = {row.id: row.alias for row in rows}
    skipped = {"id", "application_id"}

    def plain(row):
        return tuple(sorted((c.name, str(getattr(row, c.name))) for c in row.__table__.columns if c.name not in skipped))

    def owned(model):
        found = db.query(model).filter(model.application_id.in_(alias_of)).all()
        return sorted((alias_of[row.application_id], plain(row)) for row in found)

    costs = db.query(ChannelCost).filter_by(company_id=company_id).all()
    return {
        "applications": [plain(row) for row in rows],
        "results": owned(RequirementResult),
        "sessions": owned(VoiceSession),
        "scorecards": owned(InterviewScorecard),
        "probation": owned(ProbationOutcome),
        "costs": sorted(plain(row) for row in costs),
    }


def must_haves(db, job):
    return (db.query(JobRequirement)
            .filter_by(job_id=job.id, must_have=True, active=True, visibility="public")
            .order_by(JobRequirement.position).all())


def results_by_application(db, requirement):
    found = defaultdict(dict)
    for row in db.query(RequirementResult).filter_by(requirement_id=requirement.id):
        found[row.application_id][row.source] = row.status
    return found


def has_requirement(statuses):
    return statuses.get("cv") == "met" or statuses.get("interview") == "evidence"


# 1. Only sample companies


def test_a_non_sample_company_is_refused_and_nothing_is_written(db):
    real = Company(slug="real-co", name="Real", is_sample=False)
    db.add(real)
    db.commit()
    make_job(db, real)
    with pytest.raises(PermissionError, match="sample"):
        simulator.simulate(db, real)
    assert db.query(Application).count() == 0
    assert db.query(ChannelCost).count() == 0


def test_the_cli_refuses_a_non_sample_company_and_names_the_rule(db, capsys):
    real = Company(slug="real-co", name="Real", is_sample=False)
    db.add(real)
    db.commit()
    make_job(db, real)
    assert main(["simulate-hiring", "--company", "real-co", "--seed", "42"]) != 0
    assert "is_sample" in capsys.readouterr().err
    assert db.query(Application).count() == 0


def test_the_cli_names_an_unknown_company(capsys):
    assert main(["simulate-hiring", "--company", "nobody"]) != 0
    assert "nobody" in capsys.readouterr().err


def test_the_cli_writes_rows_for_a_sample_company(db, company, job, capsys):
    assert main(["simulate-hiring", "--company", SLUG, "--seed", "42"]) == 0
    db.expire_all()
    assert len(simulated_rows(db, company.id)) == 240
    assert "240" in capsys.readouterr().out


def test_a_sample_company_with_no_published_job_gets_a_clear_error(db, company, capsys):
    make_job(db, company, status="draft")
    with pytest.raises(ValueError, match="published"):
        simulator.simulate(db, company)
    assert main(["simulate-hiring", "--company", SLUG]) != 0
    assert "published" in capsys.readouterr().err


# 2. Rows go through the real tables


def test_rows_reach_every_real_table(db, company, job):
    summary = simulator.simulate(db, company, seed=42, count=240)
    rows = simulated_rows(db, company.id)
    assert len(rows) == 240 and all(row.is_simulated and row.job_id == job.id and row.job_version == 3 for row in rows)
    assert summary.applications == 240
    assert summary.hires == sum(row.final_outcome == "hired" for row in rows)
    assert summary.probation_outcomes == db.query(ProbationOutcome).filter_by(company_id=company.id).count() > 0
    assert summary.channel_costs == db.query(ChannelCost).filter_by(company_id=company.id).count() > 0
    assert summary.requirement_results == db.query(RequirementResult).count() > 0

    assert {row.cv_status for row in rows} == {"meets", "not_met"}
    assert {"invited", "withdrawn", "declined_recording", "ready_for_hr"} == {row.stage for row in rows}
    assert {"pending", "approved", "rejected"} == {row.hr_decision for row in rows}
    assert {"hired", "not_hired", "offer_declined"} <= {row.final_outcome for row in rows}
    assert {row.interview_band for row in rows} == {"many", "few", None}
    assert any(row.fast_tracked for row in rows)


def test_rows_are_consistent_with_the_rules_of_the_real_flow(db, company, job):
    simulator.simulate(db, company)
    active = db.query(JobRequirement).filter_by(job_id=job.id, active=True).all()
    musts = {row.id for row in active if row.must_have}
    with_scorecard = {row.application_id for row in db.query(InterviewScorecard)}
    with_session = {row.application_id for row in db.query(VoiceSession).filter_by(status="completed", purpose="screening")}
    on_probation = {row.application_id for row in db.query(ProbationOutcome)}
    for row in simulated_rows(db, company.id):
        cv = {r.requirement_id: r.status for r in db.query(RequirementResult).filter_by(application_id=row.id, source="cv")}
        assert set(cv) == {requirement.id for requirement in active}
        assert (row.cv_status == "meets") == all(cv[must] == "met" for must in musts)
        if row.hr_decision != "pending":
            assert row.stage == "ready_for_hr" and row.hr_decided_at is not None
        if row.interview_band is not None:
            assert row.analysis_status == "done"
        assert (row.id in with_session) == (row.interview_band is not None)
        if row.fast_tracked:
            assert row.id not in with_session and row.stage == "ready_for_hr"
        if row.final_outcome is not None:
            assert row.hr_decision == "approved" and row.id in with_scorecard
        assert (row.id in on_probation) == (row.final_outcome == "hired")


def test_only_published_jobs_are_used_and_the_count_is_shared_between_them(db, company, job):
    second = make_job(db, company, title="Frontend")
    make_job(db, company, title="Draft", status="draft")
    simulator.simulate(db, company, count=241)
    per_job = Counter(row.job_id for row in simulated_rows(db, company.id))
    assert per_job == {job.id: 121, second.id: 120}


def test_costs_cover_three_months_with_one_channel_left_empty(db, company, job):
    simulator.simulate(db, company)
    rows = db.query(ChannelCost).filter_by(company_id=company.id).all()
    assert {row.job_id for row in rows} == {job.id}
    assert all(row.amount_vnd > 0 and row.source == models_insights.SIMULATED_COST_SOURCE for row in rows)
    months = {row.period_month for row in rows}
    assert len(months) == 3 and all(len(month) == 7 and month[4] == "-" for month in months)
    per_channel = Counter(row.channel for row in rows)
    assert set(per_channel.values()) == {3}
    applied = {row.source_channel for row in simulated_rows(db, company.id)}
    assert len(applied - set(per_channel)) == 1, "one channel with applications has no cost, so 'not entered' shows"


# 3. No AI


def test_no_ai_call_is_made(db, company, job, monkeypatch):
    calls = []
    for name in ("generate_text", "generate_structured", "embed"):
        monkeypatch.setattr(gateway, name, lambda *args, _name=name, **kwargs: calls.append(_name))
    simulator.simulate(db, company)
    assert calls == []
    assert db.query(AIUsageLog).count() == 0


def test_startup_recovery_leaves_simulated_rows_alone_so_it_never_starts_ai_work(db, company, job):
    """These two pick up by stage alone, and an analysis of a row with no transcript must not be queued."""
    simulator.simulate(db, company)
    before = snapshot(db, company.id)
    assert analysis.requeue_interrupted() == []
    assert cv_processing.fail_interrupted() == 0
    db.expire_all()
    assert snapshot(db, company.id) == before


# 4. Reproducible


def test_the_same_seed_gives_identical_rows_and_another_seed_does_not(db, company, job):
    simulator.simulate(db, company, seed=42)
    first = snapshot(db, company.id)
    simulator.simulate(db, company, seed=42)
    db.expire_all()
    assert snapshot(db, company.id) == first
    simulator.simulate(db, company, seed=7)
    db.expire_all()
    assert snapshot(db, company.id) != first


# 5. Channels differ on purpose


def test_the_biggest_channel_is_not_the_one_hr_approves_most(db, company, job):
    simulator.simulate(db, company)
    rows = simulated_rows(db, company.id)
    volume = Counter(row.source_channel for row in rows)
    approved = Counter(row.source_channel for row in rows if row.hr_decision == "approved")
    rates = {channel: approved[channel] / volume[channel] for channel in volume}
    assert set(volume) == {"linkedin", "referral", "university", "facebook", "topcv", "itviec"}
    biggest = volume.most_common(1)[0][0]
    best = max(rates, key=rates.get)
    assert biggest == "linkedin" and best == "referral"
    assert rates["referral"] >= 2 * rates["linkedin"]
    assert volume["referral"] < volume["university"] < volume["linkedin"]


def test_university_brings_more_hidden_gems_than_its_share(db, company, job):
    simulator.simulate(db, company)
    rows = simulated_rows(db, company.id)
    gems = Counter(row.source_channel for row in rows if row.cv_status == "not_met" and row.interview_band == "many")
    volume = Counter(row.source_channel for row in rows)
    assert gems["university"] / volume["university"] > gems["linkedin"] / volume["linkedin"]


# 6. Replaces simulated rows, keeps real ones


def test_a_second_run_replaces_simulated_rows_and_leaves_real_rows_alone(db, company, job):
    real = Application(company_id=company.id, job_id=job.id, alias="#A1", stage="ready_for_hr", cv_status="meets",
                       source_channel="linkedin", hr_decision="approved", final_outcome="hired")
    db.add(real)
    db.commit()
    requirement = must_haves(db, job)[0]
    db.add(RequirementResult(application_id=real.id, requirement_id=requirement.id, source="cv", status="met"))
    db.add(ProbationOutcome(company_id=company.id, application_id=real.id, result="passed", recorded_by=None))
    db.add(ChannelCost(company_id=company.id, job_id=job.id, channel="linkedin", period_month="2020-01",
                       amount_vnd=1000, source="manual"))
    db.commit()
    real_id = real.id

    simulator.simulate(db, company, count=50)
    summary = simulator.simulate(db, company, count=20)
    db.expire_all()

    assert summary.replaced == 50
    assert len(simulated_rows(db, company.id)) == 20
    kept = db.get(Application, real_id)
    assert (kept.alias, kept.final_outcome, kept.is_simulated) == ("#A1", "hired", False)
    assert db.query(RequirementResult).filter_by(application_id=real_id).count() == 1
    assert db.query(ProbationOutcome).filter_by(application_id=real_id).count() == 1
    assert db.query(ChannelCost).filter_by(source="manual").count() == 1
    simulated_ids = {row.id for row in simulated_rows(db, company.id)}
    for model in (RequirementResult, VoiceSession, InterviewScorecard, ProbationOutcome):
        for row in db.query(model):
            assert row.application_id == real_id or row.application_id in simulated_ids, model.__name__


def test_a_real_cost_in_a_simulated_slot_is_kept_and_the_run_does_not_fail(db, company, job):
    simulator.simulate(db, company)
    row = db.query(ChannelCost).filter_by(company_id=company.id).order_by(ChannelCost.id).first()
    slot = (row.channel, row.period_month)
    row.source, row.amount_vnd = "manual", 123
    db.commit()
    simulator.simulate(db, company)
    db.expire_all()
    kept = db.query(ChannelCost).filter_by(channel=slot[0], period_month=slot[1]).one()
    assert (kept.source, kept.amount_vnd) == ("manual", 123)


def test_another_companys_simulated_rows_are_left_alone(db, company, job):
    other = Company(slug="sample-two", name="Two", is_sample=True)
    db.add(other)
    db.commit()
    make_job(db, other)
    simulator.simulate(db, other, count=10)
    simulator.simulate(db, company, count=10)
    simulator.simulate(db, company, count=5)
    assert len(simulated_rows(db, other.id)) == 10


def test_a_failed_run_keeps_the_earlier_rows(db, company, job, monkeypatch):
    simulator.simulate(db, company, count=10)
    before = snapshot(db, company.id)

    def explode(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(simulator, "_write_costs", explode)
    with pytest.raises(RuntimeError):
        simulator.simulate(db, company, count=20)
    db.expire_all()
    assert snapshot(db, company.id) == before


def test_real_aliases_are_not_affected_by_simulated_ones(db, company, job):
    simulator.simulate(db, company, count=10)
    assert applications.next_alias(db, company.id) == "#A1"


# 7. No personal data


def test_simulated_rows_hold_no_personal_data(db, company, job):
    simulator.simulate(db, company)
    for row in simulated_rows(db, company.id):
        assert row.alias.startswith("#S")
        assert row.candidate_user_id is None and row.cv_text_raw is None
        assert row.cv_text_blind is None and row.cv_file_path is None and row.hr_decided_by is None
    assert all(row.quote is None for row in db.query(RequirementResult))
    for session in db.query(VoiceSession):
        assert session.owner_user_id is None and session.plan is None
    assert all(row.recorded_by is None for row in db.query(ProbationOutcome))
    assert all(row.manager_user_id is None and row.notes == "" for row in db.query(InterviewScorecard))


# 8. Requirements differ on purpose, so Reality Check has a story


@pytest.mark.parametrize("seed", [42, 7, 123])
def test_a_must_have_is_missed_by_many_yet_common_among_hires_who_passed_probation(db, company, job, seed):
    simulator.simulate(db, company, seed=seed)
    rows = simulated_rows(db, company.id)
    passed = {row.application_id for row in db.query(ProbationOutcome).filter_by(result="passed")}
    assert len(passed) >= 10
    requirement = must_haves(db, job)[0]
    results = results_by_application(db, requirement)
    missed = sum(results[row.id]["cv"] != "met" for row in rows)
    assert missed / len(rows) >= 0.5
    held = sum(has_requirement(results[application_id]) for application_id in passed)
    assert held / len(passed) >= 0.7


def test_another_must_have_is_rarely_held_by_hires_so_the_rule_can_suggest_relaxing_it(db, company, job):
    simulator.simulate(db, company, seed=42)
    rows = simulated_rows(db, company.id)
    hired = [row.id for row in rows if row.final_outcome == "hired"]
    passed = {row.application_id for row in db.query(ProbationOutcome).filter_by(result="passed")}
    assert len(hired) >= 10, "Reality Check says 'not enough data' under 10 hires"
    requirement = must_haves(db, job)[-1]
    results = results_by_application(db, requirement)
    assert sum(results[row.id]["cv"] != "met" for row in rows) / len(rows) >= 0.5
    assert sum(has_requirement(results[application_id]) for application_id in hired) / len(hired) < 0.3
    assert sum(not has_requirement(results[application_id]) for application_id in passed) >= 5


def test_a_job_with_one_must_have_still_gets_consistent_rows(db, company):
    job = Job(company_id=company.id, title="One", slug="one", status="published", version=1, interview_languages=[])
    db.add(job)
    db.commit()
    db.add(JobRequirement(company_id=company.id, job_id=job.id, text="Only", must_have=True, position=0))
    db.commit()
    simulator.simulate(db, company, count=40)
    assert {row.cv_status for row in simulated_rows(db, company.id)} == {"meets", "not_met"}
    assert {row.language for row in db.query(VoiceSession)} == {"en"}


def test_a_job_with_no_must_have_is_labelled_meets_as_the_real_rule_does(db, company):
    job = Job(company_id=company.id, title="None", slug="none", status="published", version=1, interview_languages=["en"])
    db.add(job)
    db.commit()
    db.add(JobRequirement(company_id=company.id, job_id=job.id, text="Nice", must_have=False, position=0))
    db.commit()
    simulator.simulate(db, company, count=20)
    assert {row.cv_status for row in simulated_rows(db, company.id)} == {"meets"}


def test_a_confidential_must_have_gets_no_interview_result_as_in_the_real_analysis(db, company, job):
    secret = JobRequirement(company_id=company.id, job_id=job.id, text="Secret", must_have=True, position=9,
                            visibility="confidential")
    db.add(secret)
    db.commit()
    simulator.simulate(db, company, count=40)
    assert db.query(RequirementResult).filter_by(requirement_id=secret.id, source="interview").count() == 0
    assert db.query(RequirementResult).filter_by(requirement_id=secret.id, source="cv").count() == 40


# 9. Simulated rows stay out of the Block 3 board and retention figures


def _board_ids(body):
    return {card["id"] for group in (*body["cells"].values(), *body["lanes"].values()) for card in group}


def test_simulated_applications_never_appear_on_the_board(db, company, job):
    real = Application(company_id=company.id, job_id=job.id, alias="#A1", stage="ready_for_hr", cv_status="meets",
                       interview_band="many")
    db.add(real)
    db.commit()
    simulator.simulate(db, company)
    assert _board_ids(board.job_board(db, company.id, job.id)) == {real.id}


def test_simulated_applications_cannot_be_opened_or_decided_from_the_board_routes(db, company, job):
    user = make_user(db, "hr@sample.test")
    db.add(CompanyMember(company_id=company.id, user_id=user.id, role="hr"))
    db.commit()
    simulator.simulate(db, company, count=40)
    application = next(row for row in simulated_rows(db, company.id)
                       if row.stage == "ready_for_hr" and row.hr_decision == "pending")
    api = TestClient(create_app())
    headers = auth_header(user.email)
    base = f"/api/companies/{company.id}"
    assert api.get(f"{base}/applications/{application.id}", headers=headers).status_code == 404
    response = api.post(f"{base}/jobs/{job.id}/decisions/bulk", headers=headers,
                        json={"application_ids": [application.id]})
    assert response.status_code == 404
    db.expire_all()
    assert db.get(Application, application.id).hr_decision == "pending"


def test_retention_figures_leave_simulated_rows_out(db, company, job):
    simulator.simulate(db, company)
    far_ahead = datetime.now(timezone.utc) + timedelta(days=3650)
    counts = retention.counts(db, company, now=far_ahead)
    assert (counts["awaiting_deletion"], counts["due_now"], counts["anonymized"]) == (0, 0, 0)


def test_simulated_rows_keep_their_figures_through_retention_and_a_new_run_clears_its_audit_rows(db, company, job):
    simulator.simulate(db, company)
    decisions = Counter(row.hr_decision for row in simulated_rows(db, company.id))
    far_ahead = datetime.now(timezone.utc) + timedelta(days=3650)
    assert retention.run(db, now=far_ahead) > 0
    db.expire_all()
    assert Counter(row.hr_decision for row in simulated_rows(db, company.id)) == decisions
    assert retention.counts(db, company, now=far_ahead)["anonymized"] == 0
    assert db.query(AuditLog).filter_by(action=retention.ANONYMIZED).count() > 0
    simulator.simulate(db, company)
    db.expire_all()
    assert db.query(AuditLog).filter_by(action=retention.ANONYMIZED).count() == 0


# The tables the later tasks build on


def test_the_measurement_tables_have_the_columns_the_spec_names():
    expected = {
        "channel_costs": {"id", "company_id", "job_id", "channel", "period_month", "amount_vnd", "source"},
        "rejection_feedbacks": {"id", "company_id", "application_id", "language", "draft", "status", "approved_by",
                                "sent_at", "created_at"},
        "learning_resources": {"id", "company_id", "skill_node_id", "title", "url", "provider", "language", "created_by"},
        "talent_pool_entries": {"id", "company_id", "candidate_user_id", "source_application_id", "consent_id",
                                "expires_at", "status", "retained_cv_text", "embedding", "embedding_model"},
        "onboarding_plans": {"id", "company_id", "application_id", "employee_user_id", "used_interview_data", "status",
                             "approved_by"},
        "onboarding_items": {"id", "plan_id", "phase", "title", "source_node_id", "learning_resource_id",
                             "owner_user_id", "done_at"},
        "probation_outcomes": {"id", "company_id", "application_id", "result", "recorded_by", "recorded_at"},
    }
    inspector = inspect(engine)
    for table, columns in expected.items():
        assert {column["name"] for column in inspector.get_columns(table)} == columns, table
    assert Base.metadata.tables["learning_resources"].c["skill_node_id"].nullable is False
    assert Base.metadata.tables["talent_pool_entries"].c["retained_cv_text"].nullable is True


def test_channel_cost_is_unique_per_company_job_channel_and_month():
    constraints = inspect(engine).get_unique_constraints("channel_costs")
    assert ["company_id", "job_id", "channel", "period_month"] in [c["column_names"] for c in constraints]


def test_no_table_stores_attrition_or_behaviour_tracking():
    for table in ("onboarding_plans", "onboarding_items", "probation_outcomes"):
        for column in Base.metadata.tables[table].columns:
            assert not any(word in column.name for word in ("attrition", "risk", "activity", "login", "monitor"))
