"""Read models for the HR board. Nothing here returns identity or the raw CV: HR reads blind text first.

What the candidate said is masked at read time until this HR member has made a logged reveal. A quote must still be
found in the transcript shown beside it, so it is checked against the masked text, and left out if it no longer fits.
"""
from app.brain.text import quote_in
from app.database.sql_models import (
    Application, AuditLog, CandidateBrief, CultureNote, CvClaim, Job, KbNode, RequirementResult, User, VoiceSession, VoiceTurn,
)
from app.hiring import identity, jobs
from app.hiring.decisions import REVEAL_ACTION
from app.hiring.state import CONSENT_WITHDRAWN, NOT_TAKEN

CELLS = {
    ("meets", "many"): "priority",
    ("meets", "few"): "strong_cv_unclear",
    ("not_met", "many"): "hidden_gem",
    ("not_met", "few"): "not_enough_evidence",
}
LANES = ("not_interviewed", "refused_recording", "withdrawn", "analysis_failed", "analyzing")
NOT_ENOUGH_EVIDENCE = "not_enough_evidence"
NOT_TAKEN_NOTE = "did not take the interview"
CONSENT_WITHDRAWN_NOTE = "withdrew consent to recording"
NO_EVIDENCE_NOTES = {NOT_TAKEN: NOT_TAKEN_NOTE, CONSENT_WITHDRAWN: CONSENT_WITHDRAWN_NOTE}
NOT_INTERVIEWED = ("invited", "session_in_progress")
ANALYZING = ("session_completed", "analyzing")


def cell_for(application) -> str | None:
    if application.stage != "ready_for_hr":
        return None
    if application.analysis_status in NO_EVIDENCE_NOTES:  # whatever the CV label says: the interview gave no evidence
        return NOT_ENOUGH_EVIDENCE
    return CELLS.get((application.cv_status, application.interview_band))


def interview_note(application) -> str | None:
    return NO_EVIDENCE_NOTES.get(application.analysis_status)


def _lane_for(application, refused_ids=frozenset()) -> str | None:
    """`refused_ids` holds the applications whose candidate declined recording. The decline moves them straight to
    ready_for_hr so HR can decide, which leaves the stage alone unable to tell them from a fast-tracked candidate."""
    stage = application.stage
    if stage == "withdrawn":
        return "withdrawn"
    if stage == "declined_recording" or (stage == "ready_for_hr" and application.id in refused_ids):
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
        "interview_note": interview_note(application),
        "hidden_text_detected": bool(application.hidden_text_detected),
        "created_at": application.created_at.isoformat() if application.created_at else None,
    }


def job_board(db, company_id: int, job_id: int) -> dict:
    query = db.query(Application).filter(Application.company_id == company_id, Application.job_id == job_id,
                                         Application.anonymized_at.is_(None))  # nothing is left to review or decide
    if hasattr(Application, "is_simulated"):
        query = query.filter(Application.is_simulated.is_(False))
    cells = {name: [] for name in CELLS.values()}
    lanes = {name: [] for name in LANES}
    refused_ids = {
        row[0] for row in db.query(AuditLog.target_id).filter(
            AuditLog.company_id == company_id, AuditLog.action == "recording_declined", AuditLog.target_type == "application")
    }
    for application in query.order_by(Application.id).all():
        name = cell_for(application)
        if name is not None:
            cells[name].append(card(application))
            continue
        lane = _lane_for(application, refused_ids)
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


def _brief_status(db, application) -> str | None:
    if application.anonymized_at is not None:
        return None
    row = (
        db.query(CandidateBrief.status)
        .filter(CandidateBrief.application_id == application.id, CandidateBrief.company_id == application.company_id)
        .order_by(CandidateBrief.id.desc()).first()
    )
    return row[0] if row else None


def _has_revealed(db, application, viewer_id: int | None) -> bool:
    if viewer_id is None:
        return False
    return db.query(AuditLog.id).filter(
        AuditLog.company_id == application.company_id, AuditLog.action == REVEAL_ACTION, AuditLog.target_type == "application",
        AuditLog.target_id == application.id, AuditLog.actor_user_id == viewer_id,
    ).first() is not None


def _candidate_terms(db, application) -> list[str]:
    user = db.get(User, application.candidate_user_id) if application.candidate_user_id else None
    return identity.registered_terms(user.full_name, user.email) if user is not None else []


def detail(db, application, viewer_id: int | None = None) -> dict:
    job = db.get(Job, application.job_id)
    turns = [] if application.analysis_status == CONSENT_WITHDRAWN else latest_turns(db, application)
    position_of = {turn.id: turn.position for turn in turns}
    masked = not _has_revealed(db, application, viewer_id)
    terms = _candidate_terms(db, application) if masked else []

    def spoken(text):
        return identity.mask_spoken(text, terms) if masked and text else text

    transcripts = {turn.position: spoken(turn.transcript) for turn in turns if turn.transcript}

    def spoken_quote(quote, position):
        shown = spoken(quote)
        if masked and shown and position in transcripts and not quote_in(shown, transcripts[position]):
            return None
        return shown

    results: dict[tuple[int, str], RequirementResult] = {}
    for row in db.query(RequirementResult).filter_by(application_id=application.id).order_by(RequirementResult.id):
        results[(row.requirement_id, row.source)] = row

    def evidence(row, with_position):
        if row is None:
            return None
        if not with_position:
            return {"status": row.status, "quote": row.quote}  # from the CV, already blind
        position = position_of.get(row.voice_turn_id)
        return {"status": row.status, "quote": spoken_quote(row.quote, position), "position": position}

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
        {"id": c.id, "text": c.text, "quote": c.quote, "status": c.status,
         "evidence_quote": spoken_quote(c.evidence_quote, position_of.get(c.voice_turn_id)),
         "position": position_of.get(c.voice_turn_id)}
        for c in db.query(CvClaim).filter_by(application_id=application.id).order_by(CvClaim.id)
    ]
    titles = {n.id: n.title for n in db.query(KbNode).filter(KbNode.company_id == application.company_id)}
    culture_notes = [
        {"value": titles.get(n.value_node_id), "note": spoken(n.note),
         "quote": spoken_quote(n.quote, position_of.get(n.voice_turn_id)), "position": position_of.get(n.voice_turn_id)}
        for n in db.query(CultureNote).filter_by(application_id=application.id).order_by(CultureNote.id)
    ]
    return {
        "id": application.id,
        "alias": application.alias,
        "anonymized": application.anonymized_at is not None,
        "identity_masked": masked,
        "job": {"id": job.id, "title": job.title},
        "stage": application.stage,
        "cell": cell_for(application),
        "cv_status": application.cv_status,
        "cv_status_reason": application.cv_status_reason,
        "cv_status_corrected": application.cv_status_corrected_by is not None,
        "cv_status_correction_reason": application.cv_status_correction_reason,
        "interview_band": application.interview_band,
        "analysis_status": application.analysis_status,
        "interview_note": interview_note(application),
        "hr_decision": application.hr_decision,
        "final_outcome": application.final_outcome,
        "brief_status": _brief_status(db, application),
        "hr_decided_at": application.hr_decided_at.isoformat() if application.hr_decided_at else None,
        "fast_tracked": bool(application.fast_tracked),
        "hidden_text_detected": bool(application.hidden_text_detected),
        "cv_text_blind": application.cv_text_blind,
        "requirements": requirements,
        "claims": claims,
        "culture_notes": culture_notes,
        "transcript": [
            {"position": t.position, "question": spoken(t.question_text), "transcript": transcripts.get(t.position),
             "transcript_status": t.transcript_status, "is_followup": bool(t.is_followup),
             "has_audio": bool(t.audio_path)}
            for t in turns
        ],
        "suggestion": {"text": spoken(application.ai_suggestion), "source": "ai"} if application.ai_suggestion else None,
    }
