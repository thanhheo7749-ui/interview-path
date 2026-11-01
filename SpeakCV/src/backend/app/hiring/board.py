"""Read models for the HR board. Nothing here returns identity or the raw CV: HR reads blind text first."""
from app.database.sql_models import (
    Application, CultureNote, CvClaim, Job, KbNode, RequirementResult, VoiceSession, VoiceTurn,
)
from app.hiring import jobs

CELLS = {
    ("meets", "many"): "priority",
    ("meets", "few"): "strong_cv_unclear",
    ("not_met", "many"): "hidden_gem",
    ("not_met", "few"): "not_enough_evidence",
}
LANES = ("not_interviewed", "refused_recording", "withdrawn", "analysis_failed", "analyzing")
NOT_INTERVIEWED = ("invited", "session_in_progress")
ANALYZING = ("session_completed", "analyzing")


def cell_for(application) -> str | None:
    if application.stage != "ready_for_hr":
        return None
    return CELLS.get((application.cv_status, application.interview_band))


def _lane_for(application) -> str | None:
    stage = application.stage
    if stage == "withdrawn":
        return "withdrawn"
    if stage == "declined_recording":
        return "refused_recording"
    if stage in NOT_INTERVIEWED:
        return "not_interviewed"
    if stage in ANALYZING:
        return "analyzing"
    if stage == "ready_for_hr":
        if application.analysis_status == "failed":
            return "analysis_failed"
        if application.fast_tracked or cell_for(application) is None:
            return "not_interviewed"
    return None


def card(application) -> dict:
    return {
        "id": application.id,
        "alias": application.alias,
        "stage": application.stage,
        "cv_status": application.cv_status,
        "interview_band": application.interview_band,
        "hr_decision": application.hr_decision,
        "fast_tracked": bool(application.fast_tracked),
        "analysis_status": application.analysis_status,
        "hidden_text_detected": bool(application.hidden_text_detected),
        "created_at": application.created_at.isoformat() if application.created_at else None,
    }


def job_board(db, company_id: int, job_id: int) -> dict:
    query = db.query(Application).filter(Application.company_id == company_id, Application.job_id == job_id)
    if hasattr(Application, "is_simulated"):
        query = query.filter(Application.is_simulated.is_(False))
    cells = {name: [] for name in CELLS.values()}
    lanes = {name: [] for name in LANES}
    for application in query.order_by(Application.id).all():
        name = cell_for(application)
        if name is not None:
            cells[name].append(card(application))
            continue
        lane = _lane_for(application)
        if lane is not None:
            lanes[lane].append(card(application))
    return {"cells": cells, "lanes": lanes}


def latest_turns(db, application) -> list[VoiceTurn]:
    session = (
        db.query(VoiceSession)
        .filter(VoiceSession.application_id == application.id, VoiceSession.company_id == application.company_id,
                VoiceSession.purpose == "screening")
        .order_by(VoiceSession.id.desc()).first()
    )
    if session is None:
        return []
    return db.query(VoiceTurn).filter(VoiceTurn.session_id == session.id).order_by(VoiceTurn.position).all()


def detail(db, application) -> dict:
    job = db.get(Job, application.job_id)
    turns = latest_turns(db, application)
    position_of = {turn.id: turn.position for turn in turns}
    results: dict[tuple[int, str], RequirementResult] = {}
    for row in db.query(RequirementResult).filter_by(application_id=application.id).order_by(RequirementResult.id):
        results[(row.requirement_id, row.source)] = row

    def evidence(row, with_position):
        if row is None:
            return None
        item = {"status": row.status, "quote": row.quote}
        if with_position:
            item["position"] = position_of.get(row.voice_turn_id)
        return item

    requirements = [
        {
            "requirement_id": requirement.id, "text": requirement.text, "must_have": bool(requirement.must_have),
            "visibility": requirement.visibility,
            "cv": evidence(results.get((requirement.id, "cv")), False),
            "interview": evidence(results.get((requirement.id, "interview")), True),
        }
        for requirement in jobs.active_requirements(db, application.job_id)
    ]
    claims = [
        {"id": c.id, "text": c.text, "quote": c.quote, "status": c.status, "evidence_quote": c.evidence_quote,
         "position": position_of.get(c.voice_turn_id)}
        for c in db.query(CvClaim).filter_by(application_id=application.id).order_by(CvClaim.id)
    ]
    titles = {n.id: n.title for n in db.query(KbNode).filter(KbNode.company_id == application.company_id)}
    culture_notes = [
        {"value": titles.get(n.value_node_id), "note": n.note, "quote": n.quote,
         "position": position_of.get(n.voice_turn_id)}
        for n in db.query(CultureNote).filter_by(application_id=application.id).order_by(CultureNote.id)
    ]
    return {
        "id": application.id,
        "alias": application.alias,
        "job": {"id": job.id, "title": job.title},
        "stage": application.stage,
        "cell": cell_for(application),
        "cv_status": application.cv_status,
        "cv_status_reason": application.cv_status_reason,
        "cv_status_corrected": application.cv_status_corrected_by is not None,
        "cv_status_correction_reason": application.cv_status_correction_reason,
        "interview_band": application.interview_band,
        "analysis_status": application.analysis_status,
        "hr_decision": application.hr_decision,
        "hr_decided_at": application.hr_decided_at.isoformat() if application.hr_decided_at else None,
        "fast_tracked": bool(application.fast_tracked),
        "hidden_text_detected": bool(application.hidden_text_detected),
        "cv_text_blind": application.cv_text_blind,
        "requirements": requirements,
        "claims": claims,
        "culture_notes": culture_notes,
        "transcript": [
            {"position": t.position, "question": t.question_text, "transcript": t.transcript,
             "transcript_status": t.transcript_status, "is_followup": bool(t.is_followup),
             "has_audio": bool(t.audio_path)}
            for t in turns
        ],
        "suggestion": {"text": application.ai_suggestion, "source": "ai"} if application.ai_suggestion else None,
    }
