"""Requirement Reality Check. Numbers come from SQL and the suggestion from a fixed rule: no AI, and it never edits a
requirement. HR acts by opening JD Studio. Real and simulated applications are never counted together."""
from dataclasses import asdict, dataclass

from sqlalchemy.orm import Session

from app.database.sql_models import (
    Application, AuditLog, Company, JobRequirement, ProbationOutcome, RequirementResult,
)

CLEAR_STATUSES = ("met", "evidence")  # a CV match, or interview evidence
TOO_STRICT_CORRECTIONS = 3
DEFAULT_LOW_PCT, DEFAULT_HIGH_PCT, DEFAULT_MIN_HIRED = 30, 70, 10
SUGGESTIONS = ("not_enough_data", "consider_nice_to_have", "review", "keep")


@dataclass
class RequirementRow:
    requirement_id: int
    text: str
    cv_miss_rate: float | None
    hired_total: int
    hired_with_requirement: int
    hr_label_corrections: int
    probation_passed_without_requirement: int
    suggestion: str
    too_strict_signal: bool
    action: dict | None

    def as_dict(self) -> dict:
        return asdict(self)


def suggestion_for(hired_total, hired_with_requirement, low_pct=DEFAULT_LOW_PCT, high_pct=DEFAULT_HIGH_PCT,
                   min_hired=DEFAULT_MIN_HIRED) -> str:
    if hired_total < min_hired:
        return "not_enough_data"
    share = hired_with_requirement / hired_total * 100
    if share < low_pct:
        return "consider_nice_to_have"
    if share <= high_pct:
        return "review"
    return "keep"


def thresholds(company: Company) -> dict:
    return {"low_pct": company.reality_low_pct, "high_pct": company.reality_high_pct,
            "min_hired": company.reality_min_hired}


def report(db: Session, company_id: int, job_id: int, simulated: bool) -> list[RequirementRow]:
    company = db.get(Company, company_id)
    limits = thresholds(company)
    applications = (db.query(Application.id, Application.final_outcome)
                    .filter(Application.company_id == company_id, Application.job_id == job_id,
                            Application.is_simulated.is_(bool(simulated))).all())
    hired = {app_id for app_id, outcome in applications if outcome == "hired"}
    application_ids = {app_id for app_id, _ in applications}
    passed = {row.application_id for row in
              db.query(ProbationOutcome.application_id)
              .filter(ProbationOutcome.company_id == company_id, ProbationOutcome.result == "passed")} & hired
    requirements = (db.query(JobRequirement)
                    .filter(JobRequirement.company_id == company_id, JobRequirement.job_id == job_id,
                            JobRequirement.must_have.is_(True), JobRequirement.active.is_(True))
                    .order_by(JobRequirement.position, JobRequirement.id).all())

    results: dict[int, list[tuple[int, str, str]]] = {r.id: [] for r in requirements}
    if application_ids and requirements:
        for row in (db.query(RequirementResult)
                    .filter(RequirementResult.requirement_id.in_(list(results)),
                            RequirementResult.application_id.in_(application_ids))):
            results[row.requirement_id].append((row.application_id, row.source, row.status))

    # A correction to "meets" is HR saying the CV label was too harsh; it counts against a requirement only when
    # that application did not meet it on the CV.
    to_meets = {row.target_id for row in
                db.query(AuditLog).filter(AuditLog.company_id == company_id, AuditLog.action == "cv_status_corrected",
                                          AuditLog.target_type == "application",
                                          AuditLog.target_id.in_(application_ids or {0}))
                if (row.payload or {}).get("to") == "meets"}

    rows = []
    for requirement in requirements:
        found = results[requirement.id]
        cv = {app_id: status for app_id, source, status in found if source == "cv"}
        holders = {app_id for app_id, _, status in found if status in CLEAR_STATUSES}
        missed = {app_id for app_id, status in cv.items() if status != "met"}
        corrections = len(to_meets & missed)
        with_requirement = len(hired & holders)
        suggestion = suggestion_for(len(hired), with_requirement, **limits)
        action = None
        if suggestion in ("consider_nice_to_have", "review"):
            action = {"type": "open_jd_studio", "job_id": job_id, "requirement_id": requirement.id}
        rows.append(RequirementRow(
            requirement_id=requirement.id, text=requirement.text,
            cv_miss_rate=round(len(missed) / len(cv), 4) if cv else None,
            hired_total=len(hired), hired_with_requirement=with_requirement, hr_label_corrections=corrections,
            probation_passed_without_requirement=len(passed - holders), suggestion=suggestion,
            too_strict_signal=corrections >= TOO_STRICT_CORRECTIONS, action=action,
        ))
    return rows
