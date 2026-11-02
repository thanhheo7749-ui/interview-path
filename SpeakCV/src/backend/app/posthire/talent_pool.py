"""The talent pool: a separate consent keeps one masked CV for 12 months, so a company can invite the person later.

The copy lives on the entry and lasts only while the entry is valid: active, within its date, and its consent standing.
The application itself still follows the Block 3 retention rule, so `retention.has_extension` stays False for it.
AI runs with no write pending, and its result is discarded if the entry ended during the call.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np
from sqlalchemy.exc import IntegrityError

from app.ai import gateway
from app.ai.types import AIError
from app.brain import vectors
from app.database.sql_models import (
    Application, Company, Consent, Job, ScreeningCache, TalentPoolEntry, User, VoiceSession,
)
from app.hiring import applications, audit, consents, decisions, identity, jobs, notify, reapply_guard, retention, screening

logger = logging.getLogger(__name__)

CHANNEL = "talent_pool"
ACTIVE, EXPIRED, LEFT = "active", "expired", "left"
# Enough to compare two CVs, and short enough for every embedding vendor's limit on one text.
EMBED_MAX_CHARS = 8000
EMBED_BATCH_SIZE = 32
# Stages where the candidate has not yet acted on an invitation.
NOT_STARTED = ("submitted", "cv_processing", "cv_failed", "invited")
UNASSESSED = "unassessed"
INVITATION = {
    "en": ("You are invited to apply for {title}",
           "{company} kept your profile with your agreement, and invites you to apply for {title}. "
           "Your next step is a short recorded interview. You can decline in the app."),
    "vi": ("Bạn được mời ứng tuyển vị trí {title}",
           "{company} đã lưu hồ sơ của bạn theo sự đồng ý của bạn, và mời bạn ứng tuyển vị trí {title}. "
           "Bước tiếp theo là một buổi phỏng vấn ngắn có ghi âm. Bạn có thể từ chối trong ứng dụng."),
}


class ConsentRequired(Exception):
    """No standing talent_pool consent to the current text."""


class NotEligible(Exception):
    """This application cannot join: the message is safe to show the candidate."""


class EntryEnded(Exception):
    pass


@dataclass(frozen=True)
class RequirementMatch:
    requirement_id: int
    text: str
    must_have: bool
    status: str
    quote: str  # verified to be in the masked CV


@dataclass(frozen=True)
class TalentMatch:
    entry_id: int
    alias: str
    similarity: float
    strength: str  # strong, partial, weak or unassessed, by the rule in _strength
    must_haves_met: int
    must_haves_total: int
    requirements: tuple[RequirementMatch, ...]


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _naive(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value


def _a_year_after(value: datetime) -> datetime:
    try:
        return value.replace(year=value.year + 1)
    except ValueError:  # 29 February
        return value.replace(year=value.year + 1, day=28)


def _is_valid(db, entry, now: datetime) -> bool:
    if entry.status != ACTIVE or not entry.retained_cv_text or _naive(entry.expires_at) <= now:
        return False
    consent = db.get(Consent, entry.consent_id)
    return consent is not None and consent.withdrawn_at is None


def _locked_entry(db, entry_id: int) -> TalentPoolEntry | None:
    # A locking read returns the latest committed row, not this transaction's snapshot.
    return (
        db.query(TalentPoolEntry).filter(TalentPoolEntry.id == entry_id)
        .populate_existing().with_for_update().first()
    )


def _locked_consent(db, consent_id: int) -> Consent | None:
    return db.query(Consent).filter(Consent.id == consent_id).populate_existing().with_for_update().first()


def _entry_of(db, application_id: int) -> TalentPoolEntry | None:
    return (
        db.query(TalentPoolEntry).filter(TalentPoolEntry.source_application_id == application_id)
        .populate_existing().with_for_update().first()
    )


# Joining


def _locked_own_application(db, application_id: int, user_id: int) -> Application:
    application = (
        db.query(Application).filter(Application.id == application_id, Application.candidate_user_id == user_id)
        .populate_existing().with_for_update().first()
    )
    if application is None or application.is_simulated:
        db.rollback()
        raise LookupError("Application not found")
    return application


def _check_eligible(db, application) -> None:
    # The same check that shows the candidate the decision, so a refusal here reveals nothing they cannot already see.
    if decisions.visible_to_candidate(application) != "rejected":
        db.rollback()
        raise NotEligible("Your profile can be kept once a decision on this application has reached you.")
    if not application.cv_text_blind:
        db.rollback()
        raise NotEligible("There is no CV on this application to keep.")


def give_consent(db, application, user, version: str, language: str | None = None) -> None:
    """Records the consent, and flushes: `opt_in` commits it. Nothing is recorded if the person is already in the pool."""
    if version != consents.VERSION:
        db.rollback()
        raise ConsentRequired
    locked = _locked_own_application(db, application.id, user.id)
    _check_eligible(db, locked)
    entry = _entry_of(db, locked.id)
    if entry is not None and _is_valid(db, entry, _now()):
        return
    consents.record(db, user.id, locked.company_id, locked.id, consents.TALENT_POOL, version, language=language)


def _usable_consent(db, application_id: int, user_id: int, entry) -> Consent | None:
    consent = (
        db.query(Consent)
        .filter(Consent.application_id == application_id, Consent.user_id == user_id,
                Consent.purpose == consents.TALENT_POOL, Consent.withdrawn_at.is_(None),
                Consent.text_version == consents.VERSION)
        .order_by(Consent.id.desc())
        .first()
    )
    # The consent behind an entry that has ended is spent: joining again takes a new one.
    return None if consent is None or (entry is not None and entry.consent_id == consent.id) else consent


def opt_in(db, application, user) -> TalentPoolEntry:
    """Commits, and only then embeds. An outage there still leaves the entry in the pool: matching fills it in later.

    Raises LookupError, NotEligible or ConsentRequired. Each application has one row, so joining again updates it.
    """
    user_id = user.id
    locked = _locked_own_application(db, application.id, user_id)
    application_id = locked.id
    now = _now()
    entry = _entry_of(db, application_id)
    if entry is not None and _is_valid(db, entry, now):
        db.commit()
        return entry
    _check_eligible(db, locked)
    consent = _usable_consent(db, application_id, user_id, entry)
    if consent is None:
        db.rollback()
        raise ConsentRequired
    if entry is None:
        entry = TalentPoolEntry(company_id=locked.company_id, candidate_user_id=user_id, source_application_id=application_id)
        db.add(entry)
    entry.consent_id = consent.id
    entry.expires_at = _a_year_after(now)
    entry.status = ACTIVE
    entry.retained_cv_text = locked.cv_text_blind
    entry.embedding = None
    entry.embedding_model = None
    db.flush()
    entry_id = entry.id
    audit.record(db, locked.company_id, user_id, "talent_pool_joined", "talent_pool_entry", entry_id)
    db.commit()
    _embed_entries(db, [entry_id], locked.company_id)
    return db.get(TalentPoolEntry, entry_id)


def _embed_entries(db, entry_ids: list[int], company_id: int) -> None:
    """Never leaves an AI error behind: a row with no embedding is simply not matched until a later try works."""
    for start in range(0, len(entry_ids), EMBED_BATCH_SIZE):
        rows = (
            db.query(TalentPoolEntry.id, TalentPoolEntry.retained_cv_text)
            .filter(TalentPoolEntry.id.in_(entry_ids[start:start + EMBED_BATCH_SIZE]),
                    TalentPoolEntry.retained_cv_text.isnot(None))
            .all()
        )
        db.commit()  # hold no snapshot or lock during a slow call
        if not rows:
            continue
        try:
            result = gateway.embed([text[:EMBED_MAX_CHARS] for _, text in rows], "document", "talent_pool_embed", company_id)
        except AIError as exc:
            logger.warning("Could not embed talent pool entries: %s", type(exc).__name__)
            return
        for (entry_id, text), vector in zip(rows, result.vectors):
            entry = _locked_entry(db, entry_id)
            # The candidate may have left during the call: an embedding is derived from the CV, so it goes too.
            if entry is not None and entry.status == ACTIVE and entry.retained_cv_text == text:
                entry.embedding = vectors.encode(vector)
                entry.embedding_model = result.model
            db.commit()


# Ending. There is one way out, whatever the reason


def _drop_cache(db, blind_hash: str) -> None:
    """A cache row holds quotes from the CV. One still in use by an application follows that application's rules."""
    if db.query(Application.id).filter(Application.cv_blind_hash == blind_hash).first() is None:
        db.query(ScreeningCache).filter(ScreeningCache.blind_hash == blind_hash).delete(synchronize_session=False)


def _retract_unstarted_invitations(db, entry, blind_hash: str) -> None:
    """An invitation the person has not acted on holds another copy of this CV, on the basis of this same consent."""
    rows = (
        db.query(Application)
        .filter(Application.company_id == entry.company_id, Application.candidate_user_id == entry.candidate_user_id,
                Application.source_channel == CHANNEL, Application.cv_blind_hash == blind_hash,
                Application.stage.in_(NOT_STARTED), Application.hr_decision == "pending",
                Application.anonymized_at.is_(None))
        .populate_existing().with_for_update().all()
    )
    for application in rows:
        if db.query(VoiceSession.id).filter_by(application_id=application.id).first() is None:
            # No file and no audio to delete, so this can share the caller's transaction.
            retention.anonymize_application(db, application, trigger=retention.TRIGGER_CANDIDATE, commit=False)


def _end(db, entry, status: str, *, retract: bool, source_is_gone: bool) -> None:
    """Deletes the copy, and what was derived from it. Flushes; the caller commits.

    Once the application is anonymized this row is the last link between the person and it, so the row goes too.
    """
    company_id, entry_id = entry.company_id, entry.id
    text = entry.retained_cv_text
    was_active = entry.status == ACTIVE
    if was_active:
        entry.status = status
    entry.retained_cv_text = None
    entry.embedding = None
    entry.embedding_model = None
    db.flush()
    if text:
        blind_hash = identity.hash_of(text)
        if retract:
            _retract_unstarted_invitations(db, entry, blind_hash)
        _drop_cache(db, blind_hash)
    if was_active:
        audit.record(db, company_id, None, "talent_pool_ended", "talent_pool_entry", entry_id, payload={"status": status})
    if source_is_gone:
        consent = db.get(Consent, entry.consent_id)
        if consent is not None:
            consent.user_id = None
        db.delete(entry)
        db.flush()


def _source_is_gone(db, entry) -> bool:
    return db.get(Application, entry.source_application_id).anonymized_at is not None


def end_for_withdrawn_consent(db, consent) -> None:
    """Called by consents.withdraw, so every way of withdrawing ends the entry and deletes the CV at once."""
    entry = db.query(TalentPoolEntry).filter(TalentPoolEntry.consent_id == consent.id).populate_existing().with_for_update().first()
    if entry is not None and entry.status == ACTIVE:
        _end(db, entry, LEFT, retract=True, source_is_gone=_source_is_gone(db, entry))


def leave(db, entry_id: int, user) -> str:
    """Commits, and returns the entry's status. Doing it twice changes nothing. Raises LookupError for another's entry.

    One edge: an entry whose application was anonymized has no row left after leaving, so a second call finds nothing.
    """
    user_id = user.id
    db.commit()  # the locks below must read what other sessions committed
    entry = db.query(TalentPoolEntry).filter(TalentPoolEntry.id == entry_id, TalentPoolEntry.candidate_user_id == user_id).first()
    if entry is None:
        db.rollback()
        raise LookupError("Entry not found")
    consent_id = entry.consent_id
    # Consent first, then entry: the order withdrawing takes, so the two cannot deadlock.
    consent = _locked_consent(db, consent_id)
    entry = _locked_entry(db, entry_id)
    if entry is None:
        db.rollback()
        raise LookupError("Entry not found")
    status = LEFT if entry.status == ACTIVE else entry.status
    if consent.withdrawn_at is None:
        company_id = consent.company_id
        consents.withdraw(db, consent_id, user_id)
        # A consent with no user left belongs to an anonymized application, so this row must not name them either.
        audit.record(db, company_id, user_id if consent.user_id else None, "consent_withdrawn", "consent", consent_id)
    else:
        end_for_withdrawn_consent(db, consent)
    db.commit()
    return status


def on_application_anonymized(db, application, user_id: int | None, *, by_candidate: bool) -> None:
    """Called by retention while it erases the application. Its consent rows are already unlinked at this point.

    A valid entry keeps its copy, and its consent goes back to the person, who must still be able to withdraw it. The
    candidate's own delete ends the entry: they asked for their data to go. Anything else has nothing left to keep.
    """
    entry = _entry_of(db, application.id)
    if entry is None:
        return
    if not by_candidate and _is_valid(db, entry, _now()):
        db.get(Consent, entry.consent_id).user_id = user_id
        return
    if by_candidate:
        consent = db.get(Consent, entry.consent_id)
        if consent is not None and consent.withdrawn_at is None:
            consent.withdrawn_at = datetime.now(timezone.utc)
    _end(db, entry, LEFT if by_candidate else EXPIRED, retract=by_candidate, source_is_gone=True)


def expire(db, now=None) -> int:
    """End every entry past its date, and any whose consent is no longer standing. Commits, one entry at a time."""
    now = _naive(now) if now is not None else _now()
    db.commit()  # end any transaction, so the list below sees what other sessions committed
    due = (
        db.query(TalentPoolEntry.id, TalentPoolEntry.consent_id)
        .join(Consent, Consent.id == TalentPoolEntry.consent_id)
        .filter(TalentPoolEntry.status == ACTIVE)
        .filter((TalentPoolEntry.expires_at <= now) | Consent.withdrawn_at.isnot(None))
        .order_by(TalentPoolEntry.id)
        .all()
    )
    count = 0
    for entry_id, consent_id in due:
        try:
            consent = _locked_consent(db, consent_id)
            entry = _locked_entry(db, entry_id)
            if entry is None or entry.status != ACTIVE or consent is None:
                db.rollback()
                continue
            withdrawn = consent.withdrawn_at is not None
            if not withdrawn and _naive(entry.expires_at) > now:
                db.rollback()
                continue
            # An invitation already made stays when the date passes: the person may have seen it and may take it up.
            _end(db, entry, LEFT if withdrawn else EXPIRED, retract=withdrawn, source_is_gone=_source_is_gone(db, entry))
            db.commit()
            count += 1
        except Exception as exc:
            db.rollback()
            logger.warning("Could not end talent pool entry %s: %s", entry_id, type(exc).__name__)
    return count


# Matching


def _job_text(db, job) -> str:
    lines = [job.title, job.description or ""]
    lines += [row.text for row in jobs.active_requirements(db, job.id)]
    return "\n".join(line for line in lines if line)[:EMBED_MAX_CHARS]


def reapply_guard_open(db, user_id: int, job_id: int, now: datetime) -> bool:
    until = reapply_guard.blocked_until(db, user_id, job_id)
    return until is None or _naive(until) <= now


def _candidate_rows(db, company_id: int, job_id: int, now: datetime) -> list:
    """Valid, real entries of this company. People already applying to this job come through that application instead."""
    since = now - timedelta(days=applications.REAPPLY_DAYS)
    recent_people = {
        user_id for (user_id,) in db.query(Application.candidate_user_id).filter(
            Application.job_id == job_id, Application.candidate_user_id.isnot(None), Application.created_at > since,
        )
    }
    rows = (
        db.query(TalentPoolEntry, Application.alias, Application.job_id, Application.created_at)
        .join(Application, Application.id == TalentPoolEntry.source_application_id)
        .join(Consent, Consent.id == TalentPoolEntry.consent_id)
        .filter(TalentPoolEntry.company_id == company_id, TalentPoolEntry.status == ACTIVE,
                TalentPoolEntry.expires_at > now, TalentPoolEntry.retained_cv_text.isnot(None),
                Consent.withdrawn_at.is_(None), Application.is_simulated.is_(False))
        .order_by(TalentPoolEntry.id)
        .all()
    )
    return [
        row for row in rows
        if row[0].candidate_user_id not in recent_people
        and reapply_guard_open(db, row[0].candidate_user_id, job_id, now)
        # Anonymizing removes the application's link to the person, and the rule still covers the source itself.
        and not (row[2] == job_id and _naive(row[3]) > since)
    ]


def _strength(requirements, assessments) -> tuple[str, int, int]:
    """By code. strong: every must-have is met. weak: no must-have has any evidence. partial: anything between."""
    statuses = {item.requirement_id: item.status for item in assessments}
    must_haves = [row for row in requirements if row.must_have] or list(requirements)
    met = sum(statuses.get(row.id) == "met" for row in must_haves)
    evidence = sum(statuses.get(row.id) in ("met", "partial") for row in must_haves)
    if must_haves and met == len(must_haves):
        return "strong", met, len(must_haves)
    return ("partial" if evidence else "weak"), met, len(must_haves)


def _reassess(db, job_id: int, company_id: int, entry_id: int, text: str):
    def still_wanted(session) -> bool:
        entry = _locked_entry(session, entry_id)
        return entry is not None and _is_valid(session, entry, _now())

    return screening.assess_text(db, job_id, company_id, text, identity.hash_of(text), still_wanted)


def matches(db, company_id: int, job_id: int, top_k: int = 10) -> list[TalentMatch]:
    """Rank by cosine, then assess the top matches against this job. Commits, and holds nothing during AI calls.

    Raises LookupError for a job outside the company, and an AI error if the job cannot be embedded. A failed
    assessment leaves that match `unassessed`, as a best guess must not pass for a result.
    """
    db.commit()  # the lists below must see what other sessions committed
    job = db.query(Job).filter(Job.id == job_id, Job.company_id == company_id).first()
    if job is None:
        raise LookupError("Job not found")
    if not _candidate_rows(db, company_id, job_id, _now()):
        db.commit()
        return []
    job_text = _job_text(db, job)
    db.commit()
    embedded = gateway.embed([job_text], "query", "talent_pool_query", company_id)
    query = np.asarray(embedded.vectors[0], dtype="<f4")

    stale = [row[0].id for row in _candidate_rows(db, company_id, job_id, _now()) if row[0].embedding_model != embedded.model or row[0].embedding is None]
    if stale:
        _embed_entries(db, stale, company_id)

    now = _now()
    scored = []
    for entry, alias, *_ in _candidate_rows(db, company_id, job_id, now):
        if entry.embedding is None or entry.embedding_model != embedded.model:
            continue
        vector = vectors.decode(entry.embedding)
        if vector.size == query.size:
            scored.append((float(vectors.cosine_matrix(query, vector[np.newaxis, :])[0]), entry.id, entry.candidate_user_id,
                           alias, entry.retained_cv_text))
    scored.sort(key=lambda item: (-item[0], item[1]))
    requirements = [
        (row.id, row.text, bool(row.must_have)) for row in jobs.active_requirements(db, job_id)
    ]
    db.commit()

    results, seen_people, audit_rows = [], set(), []
    for similarity, entry_id, person, alias, text in scored:
        if person in seen_people:
            continue  # someone who applied twice is one person to HR
        seen_people.add(person)
        if len(results) == top_k:
            break
        try:
            assessed = _reassess(db, job_id, company_id, entry_id, text)
        except screening.ApplicationDeleted:
            continue
        except AIError as exc:
            logger.warning("Could not assess talent pool entry %s: %s", entry_id, type(exc).__name__)
            results.append(TalentMatch(entry_id, alias, round(similarity, 4), UNASSESSED, 0, 0, ()))
            continue
        audit_rows.append(assessed)
        results.append(_match(entry_id, alias, similarity, requirements, assessed))
    return _still_valid(db, company_id, job_id, results, audit_rows)


def _match(entry_id, alias, similarity, requirements, assessed) -> TalentMatch:
    strength, met, total = _strength(assessed.assessed_requirements, assessed.requirements)
    details = {row[0]: row for row in requirements}
    return TalentMatch(
        entry_id, alias, round(similarity, 4), strength, met, total,
        tuple(
            RequirementMatch(item.requirement_id, details[item.requirement_id][1], details[item.requirement_id][2],
                             item.status, item.quote)
            for item in assessed.requirements if item.requirement_id in details
        ),
    )


def _still_valid(db, company_id: int, job_id: int, results: list, assessments: list) -> list[TalentMatch]:
    """An answer from the cache takes no lock, and someone can leave while later entries are assessed."""
    db.commit()
    now = _now()
    wanted = {row[0].id for row in _candidate_rows(db, company_id, job_id, now)}
    fresh = [item for item in assessments if not item.cache_hit]
    if fresh:
        audit.record(
            db, company_id, None, "talent_matches_assessed", "job", job_id,
            payload={"assessed": len(fresh), "verification_failures": sum(item.verification_failures for item in fresh)},
            ai_provider=fresh[0].provider, ai_model=fresh[0].model, prompt_version=fresh[0].prompt_version,
        )
    db.commit()
    return [match for match in results if match.entry_id in wanted]


# Inviting


def _invite_once(db, entry_id: int, job_id: int, candidate_id: int, user_id: int) -> Application:
    # The same lock create_application takes, so this and the person's own application to this job are one after the other.
    if db.query(User.id).filter(User.id == candidate_id).with_for_update().first() is None:
        raise LookupError("Entry not found")
    entry = _locked_entry(db, entry_id)
    job = db.get(Job, job_id)
    if entry is None or job is None or entry.company_id != job.company_id:
        raise LookupError("Entry not found")
    source = db.get(Application, entry.source_application_id)
    if source.is_simulated:
        raise LookupError("Entry not found")
    now = _now()
    if not _is_valid(db, entry, now):
        raise EntryEnded
    if job.status != "published":
        raise applications.JobNotOpen
    applications.check_reapply(db, candidate_id, job_id)
    if source.job_id == job_id and _naive(source.created_at) > now - timedelta(days=applications.REAPPLY_DAYS):
        raise applications.AlreadyApplied(_naive(source.created_at) + timedelta(days=applications.REAPPLY_DAYS))
    text = entry.retained_cv_text
    application = Application(
        company_id=job.company_id, job_id=job_id, job_version=job.version, candidate_user_id=candidate_id,
        alias=applications.next_alias(db, job.company_id), source_channel=CHANNEL, stage="submitted",
        cv_text_blind=text, cv_blind_hash=identity.hash_of(text), hidden_text_detected=bool(source.hidden_text_detected),
    )
    db.add(application)
    db.flush()
    company = db.get(Company, job.company_id)
    language = company.default_locale if company.default_locale in INVITATION else "en"
    subject, body = INVITATION[language]
    notify.enqueue(db, job.company_id, candidate_id, "invited_from_pool", language,
                   subject.format(title=job.title), body.format(title=job.title, company=company.name),
                   application_id=application.id)
    audit.record(db, job.company_id, user_id, "talent_pool_invited", "application", application.id, payload={"entry_id": entry_id})
    db.commit()
    return application


def invite(db, entry, job, user_id: int) -> Application:
    """A new application from the retained text, with nothing carried over. Commits. The caller starts the CV job.

    Raises LookupError (404), EntryEnded (409), applications.JobNotOpen (409) or applications.AlreadyApplied (409).
    """
    entry_id, job_id, candidate_id = entry.id, job.id, entry.candidate_user_id
    last_error = None
    for _ in range(applications.ALIAS_ATTEMPTS):
        db.rollback()
        try:
            return _invite_once(db, entry_id, job_id, candidate_id, user_id)
        except IntegrityError as exc:  # two applications took the same alias
            last_error = exc
        except Exception:
            db.rollback()
            raise
    db.rollback()
    raise last_error
