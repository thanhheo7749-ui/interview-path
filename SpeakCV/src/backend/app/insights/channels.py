"""Channel Intelligence: which channels produce people HR approves, and at what cost. Every figure is computed here."""
from dataclasses import asdict, dataclass, field

from sqlalchemy import and_, case, exists, func
from sqlalchemy.orm import Session

from app.database.models_insights import SIMULATED_COST_SOURCE
from app.database.sql_models import Application, ChannelCost, InterviewScorecard, VoiceSession

DIRECT = "direct"
SMALL_SAMPLE = 30  # fewer applications than this: treat the row as a hint
AT_OR_AFTER_SESSION = ("session_completed", "analyzing", "ready_for_hr")
RATE_DIGITS = 4


@dataclass
class ChannelRow:
    channel: str
    applications: int
    cv_meets: int
    sessions_completed: int
    completion_rate: float | None  # fraction 0..1; None with no applications
    hr_approved: int
    approval_rate: float | None
    hidden_gems: int
    interviews: int
    hires: int
    cost: int | None  # None: not entered
    cost_per_approved: int | None
    small_sample: bool


@dataclass
class ChannelTable:
    rows: list[ChannelRow] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"rows": [asdict(row) for row in self.rows]}


def percent(rate: float | None) -> float | None:
    """The figure shown for a rate: percent with one decimal. Commentary is checked against this."""
    return None if rate is None else round(rate * 100, 1)


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, RATE_DIGITS) if whole else None


def _count(condition):
    return func.coalesce(func.sum(case((condition, 1), else_=0)), 0)


def _costs(db: Session, company_id: int, job_id: int, simulated: bool) -> dict[str, int]:
    on_source = ChannelCost.source == SIMULATED_COST_SOURCE if simulated else ChannelCost.source != SIMULATED_COST_SOURCE
    rows = (
        db.query(ChannelCost.channel, func.sum(ChannelCost.amount_vnd))
        .filter(ChannelCost.company_id == company_id, ChannelCost.job_id == job_id, on_source)
        .group_by(ChannelCost.channel)
        .all()
    )
    return {channel: int(total) for channel, total in rows}


def channel_table(db: Session, company_id: int, job_id: int, simulated: bool) -> ChannelTable:
    channel = func.coalesce(Application.source_channel, DIRECT)
    had_session = exists().where(VoiceSession.application_id == Application.id, VoiceSession.purpose == "screening")
    has_scorecard = exists().where(InterviewScorecard.application_id == Application.id)
    counted = (
        db.query(
            channel,
            func.count(Application.id),
            _count(Application.cv_status == "meets"),
            _count(and_(Application.stage.in_(AT_OR_AFTER_SESSION), had_session)),
            _count(Application.hr_decision == "approved"),
            _count(and_(Application.cv_status == "not_met", Application.interview_band == "many")),
            _count(has_scorecard),
            _count(Application.final_outcome == "hired"),
        )
        .filter(Application.company_id == company_id, Application.job_id == job_id,
                Application.is_simulated.is_(simulated))
        .group_by(channel)
        .all()
    )
    costs = _costs(db, company_id, job_id, simulated)
    rows = []
    seen = set()
    for name, applications, meets, completed, approved, gems, interviews, hires in counted:
        seen.add(name)
        total = costs.get(name)
        rows.append(ChannelRow(
            channel=name, applications=applications, cv_meets=int(meets), sessions_completed=int(completed),
            completion_rate=_rate(int(completed), applications), hr_approved=int(approved),
            approval_rate=_rate(int(approved), applications), hidden_gems=int(gems), interviews=int(interviews),
            hires=int(hires), cost=total,
            cost_per_approved=round(total / int(approved)) if total is not None and int(approved) else None,
            small_sample=applications < SMALL_SAMPLE,
        ))
    for name, total in costs.items():  # money spent on a channel nobody applied through
        if name not in seen:
            rows.append(ChannelRow(
                channel=name, applications=0, cv_meets=0, sessions_completed=0, completion_rate=None, hr_approved=0,
                approval_rate=None, hidden_gems=0, interviews=0, hires=0, cost=total, cost_per_approved=None,
                small_sample=True,
            ))
    rows.sort(key=lambda row: (-row.applications, row.channel))
    return ChannelTable(rows=rows)


def displayed(table: ChannelTable) -> list[dict]:
    """The rows as a reader sees them: rates as percent with one decimal. Sent to the AI and used to check its text."""
    shown = []
    for row in table.rows:
        values = asdict(row)
        values["completion_rate_pct"] = percent(values.pop("completion_rate"))
        values["approval_rate_pct"] = percent(values.pop("approval_rate"))
        shown.append(values)
    return shown
