"""Labelled demo data for sample companies. It proves the measurement mechanism, not any real effect.

Rows go through the real tables with `is_simulated=True`, or `source="simulated"` on costs. Nothing here calls AI, and
every value comes from `random.Random(seed)` or a constant, so a seed always gives the same rows.

Stages are limited to ones no background job picks up: startup recovery would queue an AI analysis for
`session_completed` or `analyzing`, and would fail `submitted` or `cv_processing`.
"""
import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.database.sql_models import (
    Application, AuditLog, CandidateBrief, ChannelCost, Consent, CultureNote, CvClaim, InterviewScorecard, Job,
    Notification, OnboardingItem, OnboardingPlan, ProbationOutcome, RejectionFeedback, RequirementResult,
    SIMULATED_COST_SOURCE, TalentPoolEntry, VoiceSession, VoiceTurn,
)
from app.hiring import decisions, jobs, screening

ALIAS_PREFIX = "#S"
# Fixed, not relative to today: a seed must give the same rows on any date.
PERIOD_MONTHS = ((2026, 8), (2026, 9), (2026, 10))
NOT_ENTERED_CHANNEL = "facebook"  # paid nothing on record, so the table shows "not entered"

# volume: share of applications. cv_meets: chance the CV meets every must-have. many_if_meets, many_if_not_met: chance of
# a strong interview. approval: multiplies BASE_APPROVAL. monthly_cost_vnd: per job.
CHANNEL_PROFILES = {
    "linkedin": {"volume": 0.38, "cv_meets": 0.15, "session": 0.58, "many_if_meets": 0.60, "many_if_not_met": 0.25,
                 "approval": 0.55, "probation_pass": 0.70, "monthly_cost_vnd": 18_000_000},
    "referral": {"volume": 0.07, "cv_meets": 0.40, "session": 0.85, "many_if_meets": 0.85, "many_if_not_met": 0.55,
                 "approval": 1.70, "probation_pass": 0.95, "monthly_cost_vnd": 5_000_000},
    "university": {"volume": 0.17, "cv_meets": 0.10, "session": 0.72, "many_if_meets": 0.55, "many_if_not_met": 0.70,
                   "approval": 0.75, "probation_pass": 0.85, "monthly_cost_vnd": 3_000_000},
    "facebook": {"volume": 0.14, "cv_meets": 0.15, "session": 0.60, "many_if_meets": 0.60, "many_if_not_met": 0.40,
                 "approval": 0.85, "probation_pass": 0.75, "monthly_cost_vnd": 0},
    "topcv": {"volume": 0.14, "cv_meets": 0.20, "session": 0.62, "many_if_meets": 0.60, "many_if_not_met": 0.40,
              "approval": 0.85, "probation_pass": 0.80, "monthly_cost_vnd": 8_000_000},
    "itviec": {"volume": 0.10, "cv_meets": 0.25, "session": 0.68, "many_if_meets": 0.70, "many_if_not_met": 0.45,
               "approval": 1.00, "probation_pass": 0.80, "monthly_cost_vnd": 10_000_000},
}
# Whatever is left after a session or fast track splits between these, and the rest stay invited without starting.
WITHDRAWN = 0.40
DECLINED = 0.25
FAST_TRACK_IF_MEETS = 0.08
PENDING = 0.08
BASE_APPROVAL = {
    "priority": 0.70, "strong_cv_unclear": 0.25, "hidden_gem": 0.75, "not_enough_evidence": 0.05, "fast_tracked": 0.80,
}
SCORECARD_IF_APPROVED = 0.90
HIRE_RECOMMENDED = 0.90
# A strong CV has other offers, so more of these decline. This is why most hires come from a CV that did not meet.
HIRED_IF_MEETS = 0.35
HIRED_IF_NOT_MET = 0.90

# The Reality Check story. Both are missed on many CVs. Hires prove the first in the interview, and rarely have the second.
PROVEN_LATER = {"cv_miss": 0.75, "evidence": 0.92}
RARELY_HELD = {"cv_miss": 0.97, "evidence": 0.04}
ORDINARY = {"cv_miss": 0.35, "evidence": 0.65}
# Must-haves other than the two above, and nice-to-haves, share this split of partial and absent answers.
PARTIAL_SHARE = 0.30
NICE_TO_HAVE_MET = 0.50


@dataclass(frozen=True)
class SimulationSummary:
    company_id: int
    seed: int
    jobs: int
    applications: int
    requirement_results: int
    sessions: int
    scorecards: int
    hires: int
    probation_outcomes: int
    channel_costs: int
    replaced: int


def _simulated_jobs(db, company_id: int) -> list[tuple[Job, list]]:
    rows = db.query(Job).filter_by(company_id=company_id, status="published").order_by(Job.id).all()
    found = [(job, jobs.active_requirements(db, job.id)) for job in rows]
    found = [(job, requirements) for job, requirements in found if requirements]
    if not found:
        raise ValueError("Simulated hiring needs a published job with requirements. Run seed-samples first.")
    return found


def _delete_earlier(db, company_id: int) -> int:
    """Named table by table, because SQLite does not enforce the cascades that MySQL does."""
    ids = [row[0] for row in db.query(Application.id).filter_by(company_id=company_id, is_simulated=True)]
    db.query(ChannelCost).filter_by(company_id=company_id, source=SIMULATED_COST_SOURCE).delete()
    if not ids:
        return 0
    session_ids = [row[0] for row in db.query(VoiceSession.id).filter(VoiceSession.application_id.in_(ids))]
    plan_ids = [row[0] for row in db.query(OnboardingPlan.id).filter(OnboardingPlan.application_id.in_(ids))]
    db.query(OnboardingItem).filter(OnboardingItem.plan_id.in_(plan_ids)).delete()
    for model in (RequirementResult, CvClaim, CultureNote):  # these point at voice turns
        db.query(model).filter(model.application_id.in_(ids)).delete()
    db.query(VoiceTurn).filter(VoiceTurn.session_id.in_(session_ids)).delete()
    # A talent pool entry points at a consent, so it goes first.
    db.query(TalentPoolEntry).filter(TalentPoolEntry.source_application_id.in_(ids)).delete()
    for model in (VoiceSession, Consent, Notification, CandidateBrief, InterviewScorecard, RejectionFeedback,
                  OnboardingPlan, ProbationOutcome):
        db.query(model).filter(model.application_id.in_(ids)).delete()
    db.query(AuditLog).filter(AuditLog.company_id == company_id, AuditLog.target_type == "application",
                              AuditLog.target_id.in_(ids)).delete()
    db.query(Application).filter(Application.id.in_(ids)).delete()
    return len(ids)


def _story_of(requirements) -> dict[int, dict]:
    public = [row for row in requirements if row.must_have and row.visibility == "public"]
    story = {row.id: ORDINARY for row in requirements if row.must_have}
    if public:
        story[public[-1].id] = RARELY_HELD
        story[public[0].id] = PROVEN_LATER  # with one must-have, this story is the one that holds
    return story


def _not_met_status(rng) -> str:
    return "partial" if rng.random() < PARTIAL_SHARE else "not_found"


def _cv_results(rng, requirements, story, want_meets: bool) -> dict[int, str]:
    statuses = {}
    for requirement in requirements:
        if not requirement.must_have:
            statuses[requirement.id] = "met" if rng.random() < NICE_TO_HAVE_MET else _not_met_status(rng)
        elif want_meets:
            statuses[requirement.id] = "met"
        elif rng.random() < story[requirement.id]["cv_miss"]:
            # Only a plain miss on a story requirement, so its miss rate reads the same however "miss" is counted.
            statuses[requirement.id] = "not_found" if story[requirement.id] is not ORDINARY else _not_met_status(rng)
        else:
            statuses[requirement.id] = "met"
    musts = [requirement.id for requirement in requirements if requirement.must_have]
    if not want_meets and musts and all(statuses[must] == "met" for must in musts):
        statuses[max(musts, key=lambda must: story[must]["cv_miss"])] = "not_found"
    return statuses


def _interview_results(rng, requirements, story, cv_statuses) -> dict[int, str]:
    """Public must-haves only, as in the real analysis. A candidate who shows it on the CV can usually talk about it."""
    statuses = {}
    for requirement in requirements:
        if not requirement.must_have or requirement.visibility != "public":
            continue
        chance = story[requirement.id]["evidence"]
        if cv_statuses[requirement.id] == "met":
            chance = max(chance, ORDINARY["evidence"])
        statuses[requirement.id] = "evidence" if rng.random() < chance else ("partial" if rng.random() < 0.5 else "none")
    return statuses


def _created_at(rng) -> datetime:
    year, month = rng.choice(PERIOD_MONTHS)
    return datetime(year, month, rng.randint(1, 28), rng.randint(8, 18), rng.randint(0, 59))


def _approval_cell(cv_status: str, band: str | None) -> str:
    if band is None:
        return "fast_tracked"
    good_cv, good_interview = cv_status == "meets", band == "many"
    if good_cv:
        return "priority" if good_interview else "strong_cv_unclear"
    return "hidden_gem" if good_interview else "not_enough_evidence"


def _simulate_application(db, rng, job, requirements, story, alias: str) -> dict[str, int]:
    channels = list(CHANNEL_PROFILES)
    channel = rng.choices(channels, weights=[CHANNEL_PROFILES[name]["volume"] for name in channels])[0]
    profile = CHANNEL_PROFILES[channel]
    cv_statuses = _cv_results(rng, requirements, story, rng.random() < profile["cv_meets"])
    results = [RequirementResult(requirement_id=key, source="cv", status=value) for key, value in cv_statuses.items()]
    cv_status, reasons = screening.label(results, requirements)
    created_at = _created_at(rng)
    application = Application(
        company_id=job.company_id, job_id=job.id, job_version=job.version, alias=alias, source_channel=channel,
        stage="invited", cv_status=cv_status, cv_status_reason=reasons or None, is_simulated=True, created_at=created_at,
    )
    db.add(application)
    db.flush()
    counts = {"sessions": 0, "scorecards": 0, "hires": 0, "probation_outcomes": 0}

    fast_tracked = cv_status == "meets" and rng.random() < FAST_TRACK_IF_MEETS
    took_session = not fast_tracked and rng.random() < profile["session"]
    if fast_tracked:
        application.stage, application.fast_tracked = "ready_for_hr", True
    elif took_session:
        application.stage, application.analysis_status = "ready_for_hr", "done"
        many = profile["many_if_meets"] if cv_status == "meets" else profile["many_if_not_met"]
        application.interview_band = "many" if rng.random() < many else "few"
        started_at = created_at + timedelta(days=rng.randint(1, 5))
        db.add(VoiceSession(
            company_id=job.company_id, purpose="screening", application_id=application.id,
            language=(job.interview_languages or ["en"])[0], status="completed", started_at=started_at,
            finished_at=started_at + timedelta(minutes=rng.randint(12, 25)),
        ))
        counts["sessions"] = 1
        results += [RequirementResult(requirement_id=key, source="interview", status=value)
                    for key, value in _interview_results(rng, requirements, story, cv_statuses).items()]
    else:
        draw = rng.random()
        if draw < WITHDRAWN:
            application.stage = "withdrawn"
        elif draw < WITHDRAWN + DECLINED:
            application.stage = "declined_recording"
    for result in results:
        result.application_id = application.id
    db.add_all(results)

    if application.stage == "ready_for_hr" and rng.random() >= PENDING:
        counts = _decide(db, rng, application, profile, created_at, counts)
    return counts


def _decide(db, rng, application, profile, created_at, counts) -> dict[str, int]:
    decided_at = created_at + timedelta(days=rng.randint(6, 12))
    cell = _approval_cell(application.cv_status, application.interview_band)
    approved = rng.random() < min(0.95, BASE_APPROVAL[cell] * profile["approval"])
    decisions.record_simulated(application, "approved" if approved else "rejected", decided_at)
    if not approved or rng.random() >= SCORECARD_IF_APPROVED:
        return counts
    recommended = rng.random() < HIRE_RECOMMENDED
    db.add(InterviewScorecard(
        company_id=application.company_id, application_id=application.id, requirement_scores=[],
        recommendation="hire" if recommended else "no_hire", notes="", submitted_at=decided_at + timedelta(days=rng.randint(3, 10)),
    ))
    counts = {**counts, "scorecards": 1}
    if not recommended:
        application.final_outcome = "not_hired"
        return counts
    hired = rng.random() < (HIRED_IF_MEETS if application.cv_status == "meets" else HIRED_IF_NOT_MET)
    application.final_outcome = "hired" if hired else "offer_declined"
    if hired:
        if rng.random() < profile["probation_pass"]:
            result = "passed"
        else:
            result = "failed" if rng.random() < 0.5 else "extended"
        db.add(ProbationOutcome(company_id=application.company_id, application_id=application.id, result=result,
                                recorded_at=decided_at + timedelta(days=60)))
        counts = {**counts, "hires": 1, "probation_outcomes": 1}
    return counts


def _write_costs(db, rng, job) -> int:
    """A real cost already in a slot keeps it: the unique key has room for one row, and real data is never replaced."""
    taken = {
        (row.channel, row.period_month)
        for row in db.query(ChannelCost.channel, ChannelCost.period_month).filter_by(company_id=job.company_id, job_id=job.id)
    }
    written = 0
    for channel, profile in CHANNEL_PROFILES.items():
        if channel == NOT_ENTERED_CHANNEL:
            continue
        for year, month in PERIOD_MONTHS:
            period_month = f"{year}-{month:02d}"
            # Drawn before the check, so a kept real cost does not change any other simulated value.
            amount = int(profile["monthly_cost_vnd"] * rng.uniform(0.8, 1.2) / 100_000) * 100_000
            if (channel, period_month) in taken:
                continue
            db.add(ChannelCost(company_id=job.company_id, job_id=job.id, channel=channel, period_month=period_month,
                               amount_vnd=amount, source=SIMULATED_COST_SOURCE))
            written += 1
    return written


def simulate(db, company, seed: int = 42, count: int = 240) -> SimulationSummary:
    """Replace the company's simulated rows, in one transaction. Commits, and rolls back on any failure."""
    if not company.is_sample:
        raise PermissionError("simulate-hiring is only allowed for sample companies (is_sample=true)")
    if count < 1:
        raise ValueError("Count must be at least 1")
    rng = random.Random(seed)
    totals = {"sessions": 0, "scorecards": 0, "hires": 0, "probation_outcomes": 0}
    try:
        targets = _simulated_jobs(db, company.id)
        replaced = _delete_earlier(db, company.id)
        results_before = db.query(RequirementResult.id).count()
        stories = {job.id: _story_of(requirements) for job, requirements in targets}
        for number in range(1, count + 1):
            job, requirements = targets[(number - 1) % len(targets)]
            counts = _simulate_application(db, rng, job, requirements, stories[job.id], f"{ALIAS_PREFIX}{number}")
            for name, value in counts.items():
                totals[name] += value
        costs = sum(_write_costs(db, rng, job) for job, _ in targets)
        db.flush()
        results = db.query(RequirementResult.id).count() - results_before
        db.commit()
    except Exception:
        db.rollback()
        raise
    return SimulationSummary(company_id=company.id, seed=seed, jobs=len(targets), applications=count,
                             requirement_results=results, channel_costs=costs, replaced=replaced, **totals)
