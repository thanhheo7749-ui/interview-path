# Omni-Channel & Non-Blind Hiring Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the hiring workflow to remove CV anonymization (display real candidate identity, contact info, raw CV, and unmasked transcripts directly), enable passwordless direct apply and HR multi-channel bulk CV import (TopCV, ITviec, LinkedIn, etc. via `.pdf`/`.docx`/`.zip`) with cross-channel deduplication and 1-click Magic Link claiming, add a `cv_hold` gate for 0% must-have CVs, support both fixed and per-application SLA interview windows, and synchronize candidate-visible statuses across HR and Manager rounds (`in_manager_round`, `hired`, `not_hired`).

**Architecture:** Extend `Job` (`interview_sla_hours`) and `Application` (`candidate_name`, `candidate_email`, `candidate_phone`, `contact_hash`, `claim_token_hash`, `invited_at`) with Alembic migration `0012_omni_channel_workflow`. Update `app/hiring/identity.py` to extract real contact details while preserving raw text without AI masking. Add `cv_hold` and `missing_contact` stages to `app/hiring/state.py`, unify candidate-visible decisions across `hr_decision` and `final_outcome`, and expose guest apply, magic-link claim, and HR bulk CV import endpoints consumed by the Next.js candidate app (`SpeakCV/src/frontend`) and React B2B portal (`interviewpath/interviewpath-demo`).

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pytest, React 18 (Vite), Next.js 16 (TypeScript).

## Global Constraints

- Git commit messages: a single line, no body, never a `Co-Authored-By` trailer. Commit only the files your task touches.
- Never print, log or commit values from `.env` files. Do not push. Do not touch Docker containers you did not start.
- Routes that call the AI gateway must not block the event loop: use plain `def`, or wrap the call in `run_in_threadpool` when the route must stay `async` because of `read_upload`.
- SQLite tests cannot show MySQL's `REPEATABLE READ` behaviour. A session that must see rows committed by another session, such as a background job, must end its own transaction first with `db.commit()` or `db.rollback()`; `db.expire_all()` does not do this.
- Every schema change ships with an Alembic migration and must pass `tests/test_migrations.py::test_head_matches_models` (`compare_metadata(context, Base.metadata) == []`).
- No CV anonymization: `identity.mask` and `identity.mask_spoken` preserve raw text without calling the AI gateway, while `identity.extract_contact_info` extracts `name`, `email`, `phone`, and `contact_hash` by deterministic regex/heuristics.
- `cv_hold` rule: When a job has active `must_have` requirements and a processed CV achieves 0 `met` and 0 `partial` across all `must_have` requirements, the application moves to `stage="cv_hold"` instead of `"invited"`. Otherwise it moves to `"invited"`.
- Interview window rule: Support both fixed job windows (`interview_window_start`..`interview_window_end`, closing `can_apply` once `now > interview_window_end`) and per-application SLA windows (`Job.interview_sla_hours` measured from `Application.invited_at`).
- Backend test runner: `cd /home/vanii/Documents/Workspace/ktech/interview-path/SpeakCV/src/backend && .venv/bin/pytest -q`.

---

### Task 1: Database Schema & State Machine (`0012_omni_channel_workflow.py`)

**Files:**
- Create: `SpeakCV/src/backend/alembic/versions/0012_omni_channel_workflow.py`
- Modify: `SpeakCV/src/backend/app/database/models_hiring.py:18-107`
- Modify: `SpeakCV/src/backend/app/hiring/state.py:1-32`
- Test: `SpeakCV/src/backend/tests/test_migrations.py`

**Interfaces:**
- Consumes: `0011_practice_context` Alembic revision, `Base` metadata.
- Produces:
  - `Job.interview_sla_hours: Column(Integer, nullable=True)`
  - `Application.candidate_name: Column(String(255), nullable=True)`
  - `Application.candidate_email: Column(String(255), nullable=True, index=True)`
  - `Application.candidate_phone: Column(String(50), nullable=True)`
  - `Application.contact_hash: Column(String(64), nullable=True, index=True)`
  - `Application.claim_token_hash: Column(String(64), nullable=True, unique=True, index=True)`
  - `Application.invited_at: Column(DateTime(timezone=True), nullable=True)`
  - `state.STAGES` and `state.TRANSITIONS` supporting `"cv_hold"` and `"missing_contact"`.

- [ ] **Step 1: Write the failing test**

Add schema and state transition assertions in `SpeakCV/src/backend/tests/test_migrations.py`:

```python
def test_omni_channel_columns_and_stages_exist(tmp_path):
    from app.hiring.state import STAGES, TRANSITIONS, advance
    from app.database.models_hiring import Application

    engine = _new_engine(tmp_path)
    with engine.begin() as connection:
        run_migrations(connection)
    inspector = inspect(engine)
    app_cols = {c["name"] for c in inspector.get_columns("applications")}
    job_cols = {c["name"] for c in inspector.get_columns("jobs")}
    assert {
        "candidate_name", "candidate_email", "candidate_phone",
        "contact_hash", "claim_token_hash", "invited_at",
    } <= app_cols
    assert "interview_sla_hours" in job_cols
    assert "cv_hold" in STAGES
    assert "missing_contact" in STAGES
    assert "cv_hold" in TRANSITIONS["cv_processing"]
    assert "invited" in TRANSITIONS["cv_hold"]
    assert "cv_processing" in TRANSITIONS["missing_contact"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/vanii/Documents/Workspace/ktech/interview-path/SpeakCV/src/backend && .venv/bin/pytest tests/test_migrations.py -v`
Expected: FAIL because columns and stages do not exist yet.

- [ ] **Step 3: Write minimal implementation**

1. In `SpeakCV/src/backend/app/database/models_hiring.py`:
   - Add `interview_sla_hours = Column(Integer, nullable=True)` to `Job`.
   - Add to `Application`:
     ```python
     candidate_name = Column(String(255), nullable=True)
     candidate_email = Column(String(255), nullable=True, index=True)
     candidate_phone = Column(String(50), nullable=True)
     contact_hash = Column(String(64), nullable=True, index=True)
     claim_token_hash = Column(String(64), nullable=True, unique=True, index=True)
     invited_at = Column(DateTime(timezone=True), nullable=True)
     ```
2. Create `SpeakCV/src/backend/alembic/versions/0012_omni_channel_workflow.py` with `revision = '0012_omni_channel_workflow'` and `down_revision = '0011_practice_context'` adding the exact columns and indexes (`ix_applications_candidate_email`, `ix_applications_contact_hash`, `ix_applications_claim_token_hash`).
3. In `SpeakCV/src/backend/app/hiring/state.py`:
   ```python
   STAGES = (
       "submitted", "missing_contact", "cv_processing", "cv_failed", "cv_hold",
       "invited", "withdrawn", "declined_recording",
       "session_in_progress", "session_completed", "analyzing", "ready_for_hr",
   )
   TRANSITIONS = {
       "submitted": {"cv_processing", "missing_contact"},
       "missing_contact": {"cv_processing", "withdrawn"},
       "cv_processing": {"invited", "cv_hold", "cv_failed", "missing_contact"},
       "cv_failed": {"cv_processing", "invited", "withdrawn"},
       "cv_hold": {"invited", "ready_for_hr", "withdrawn"},
       "invited": {"session_in_progress", "withdrawn", "declined_recording", "ready_for_hr"},
       "declined_recording": {"ready_for_hr"},
       "session_in_progress": {"session_completed", "ready_for_hr"},
       "session_completed": {"analyzing"},
       "analyzing": {"ready_for_hr", "session_completed"},
       "ready_for_hr": {"invited"},
       "withdrawn": set(),
   }
   ```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/vanii/Documents/Workspace/ktech/interview-path/SpeakCV/src/backend && .venv/bin/pytest tests/test_migrations.py -v`
Expected: PASS (including `test_head_matches_models`).

- [ ] **Step 5: Commit**

```bash
git add SpeakCV/src/backend/alembic/versions/0012_omni_channel_workflow.py SpeakCV/src/backend/app/database/models_hiring.py SpeakCV/src/backend/app/hiring/state.py SpeakCV/src/backend/tests/test_migrations.py
git commit -m "feat: add omni-channel columns and cv_hold/missing_contact stages"
```

---

### Task 2: Non-Blind CV Processing & Contact Extraction (`identity.py` & `cv_processing.py`)

**Files:**
- Modify: `SpeakCV/src/backend/app/hiring/identity.py`
- Modify: `SpeakCV/src/backend/app/hiring/cv_processing.py`
- Test: `SpeakCV/src/backend/tests/test_hiring_apply.py`

**Interfaces:**
- Consumes: `Application` columns `candidate_name`, `candidate_email`, `candidate_phone`, `contact_hash`.
- Produces:
  - `identity.ContactInfo(name: str | None, email: str | None, phone: str | None, contact_hash: str | None)`
  - `identity.extract_contact_info(text: str, fallback_name: str | None = None, fallback_email: str | None = None) -> ContactInfo`
  - `identity.mask(raw_text: str, *, company_id: int, known_terms: list[str] = ()) -> MaskResult` (returns unmasked normalized text and its SHA-256 hash, making zero AI calls)
  - `identity.mask_spoken(text: str, known_terms: list[str]) -> str` (returns unmasked normalized text).

- [ ] **Step 1: Write the failing test**

Add test in `SpeakCV/src/backend/tests/test_hiring_apply.py` verifying that:
1. `identity.extract_contact_info` extracts email, phone, name, and computes a deterministic `contact_hash`.
2. `identity.mask` and `cv_processing.run` preserve the candidate's real name, email, and phone in `cv_text_blind` and populate `application.candidate_name`, `application.candidate_email`, `application.candidate_phone`, `application.contact_hash` without calling `gateway.generate_structured` for `cv_mask`.

```python
def test_cv_processing_keeps_real_identity_and_extracts_contact(db_session):
    from app.hiring import identity
    raw = "Nguyen Van An\nEmail: an.nguyen@example.com\nPhone: 0901234567\n5 years Python FastAPI"
    info = identity.extract_contact_info(raw)
    assert info.email == "an.nguyen@example.com"
    assert info.phone == "0901234567"
    assert info.name == "Nguyen Van An"
    assert info.contact_hash is not None
    masked = identity.mask(raw, company_id=1)
    assert "Nguyen Van An" in masked.blind_text
    assert "an.nguyen@example.com" in masked.blind_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/vanii/Documents/Workspace/ktech/interview-path/SpeakCV/src/backend && .venv/bin/pytest tests/test_hiring_apply.py -k test_cv_processing_keeps_real_identity_and_extracts_contact -v`
Expected: FAIL with `AttributeError: module 'app.hiring.identity' has no attribute 'extract_contact_info'`.

- [ ] **Step 3: Write minimal implementation**

1. In `SpeakCV/src/backend/app/hiring/identity.py`:
   - Add `ContactInfo` dataclass and `extract_contact_info(text: str, fallback_name: str | None = None, fallback_email: str | None = None) -> ContactInfo`:
     - Extract first email via `_EMAIL`, normalize to lowercase.
     - Extract first phone via `_PHONE`, normalize digits.
     - Infer candidate name from `fallback_name` or the first non-empty header line of the CV that is not an email/URL/phone/heading (`CV`, `Resume`, `Curriculum Vitae`).
     - Compute `contact_hash = hashlib.sha256(f"{email or ''}|{ digits_phone or ''}".encode("utf-8")).hexdigest()` when either email or phone is present, else `None`.
   - Update `mask()` to normalize whitespace via `_collapse(unicodedata.normalize("NFC", raw_text))` and return `MaskResult(blind_text=collapsed, blind_hash=hash_of(collapsed))` without calling `gateway.generate_structured`.
   - Update `mask_spoken()` to return `unicodedata.normalize("NFC", text)`.
2. In `SpeakCV/src/backend/app/hiring/cv_processing.py`:
   - During `_process`, call `contact = identity.extract_contact_info(cv.text, fallback_name=user.full_name if user else None, fallback_email=user.email if user else None)`.
   - Save `application.candidate_name = contact.name`, `application.candidate_email = contact.email`, `application.candidate_phone = contact.phone`, `application.contact_hash = contact.contact_hash`.
   - Update existing tests that previously asserted `[NAME]` or `[EMAIL]` redaction in `cv_text_blind` to match the non-blind policy.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/vanii/Documents/Workspace/ktech/interview-path/SpeakCV/src/backend && .venv/bin/pytest tests/test_hiring_apply.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add SpeakCV/src/backend/app/hiring/identity.py SpeakCV/src/backend/app/hiring/cv_processing.py SpeakCV/src/backend/tests/
git commit -m "feat: remove CV anonymization and extract real candidate contact info"
```

---

### Task 3: Smart `cv_hold` Gate, Flexible Interview Window (Fixed + SLA), and Unpenalized Pre-Interview Withdraw

**Files:**
- Modify: `SpeakCV/src/backend/app/hiring/cv_processing.py`
- Modify: `SpeakCV/src/backend/app/hiring/interview_window.py`
- Modify: `SpeakCV/src/backend/app/hiring/applications.py`
- Modify: `SpeakCV/src/backend/app/routers/public_jobs.py`
- Modify: `SpeakCV/src/backend/app/routers/jobs_hr.py`
- Modify: `SpeakCV/src/backend/app/routers/screening.py`
- Modify: `SpeakCV/src/backend/app/schemas/jobs.py`
- Test: `SpeakCV/src/backend/tests/test_hiring_apply.py`

**Interfaces:**
- Consumes: `Job.interview_sla_hours`, `Application.invited_at`, `Application.stage == "cv_hold"`.
- Produces:
  - `cv_processing._assess_and_label`: moves to `"cv_hold"` if the job has at least 1 `must_have` requirement and 0 `must_have` requirements are `"met"` or `"partial"`; otherwise moves to `"invited"` and sets `application.invited_at = datetime.now(timezone.utc)`.
  - `interview_window.is_open(job, now, application=None) -> bool`: checks both fixed window (`interview_window_start`..`interview_window_end`) and per-application SLA (`application.invited_at + timedelta(hours=job.interview_sla_hours)`).
  - `interview_window.can_apply_now(job, now) -> bool`: returns `False` when `job.scheduling_enabled` and `job.interview_window_end` is in the past.
  - `applications.check_reapply`: ignores withdrawn applications (`stage == "withdrawn"`) that have no `VoiceSession`.

- [ ] **Step 1: Write the failing test**

Add tests in `SpeakCV/src/backend/tests/test_hiring_apply.py`:
1. `test_zero_must_have_cv_enters_cv_hold`: A CV with `not_found` on all `must_have` requirements lands in `stage == "cv_hold"` and does not enqueue an invitation notification.
2. `test_withdrawn_before_interview_can_reapply_immediately`: Withdrawing in `"invited"` or `"cv_hold"` with no `VoiceSession` does not write a `ReapplyGuard` block and allows immediate re-application.
3. `test_expired_fixed_window_closes_public_apply_and_sla_hours_gates_screening`: Verify `can_apply` is `False` after `interview_window_end`, and `interview_sla_hours` gates screening start relative to `application.invited_at`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/vanii/Documents/Workspace/ktech/interview-path/SpeakCV/src/backend && .venv/bin/pytest tests/test_hiring_apply.py -k "cv_hold or withdrawn_before_interview or sla_hours" -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

1. In `SpeakCV/src/backend/app/hiring/cv_processing.py`:
   - In `_assess_and_label`: check `must_haves = [r for r in result.requirements if r.must_have]`. If `must_haves` is non-empty and every matching assessment in `result.assessed_requirements` has status `"not_found"`, `advance(application, "cv_hold")`; otherwise `advance(application, "invited")` and set `application.invited_at = datetime.now(timezone.utc)`.
   - Only enqueue the `"invited"` notification in `_process` when `application.stage == "invited"`.
2. In `SpeakCV/src/backend/app/hiring/interview_window.py`:
   - Update `is_open(job, now, application=None)` to check fixed window (if `job.scheduling_enabled` and `interview_window_start`/`end` are set) AND check `job.interview_sla_hours` against `application.invited_at` (if `application is not None and job.interview_sla_hours and application.invited_at`).
   - Add `can_apply_now(job, now) -> bool` returning `job.status == "published" and not (job.scheduling_enabled and job.interview_window_end is not None and to_utc(now) > to_utc(job.interview_window_end))`.
   - Update `payload(job, application=None)` to compute the effective `start`/`end` for an application when `job.interview_sla_hours` is configured.
3. In `SpeakCV/src/backend/app/hiring/applications.py`:
   - In `check_reapply`: filter out `Application.stage == "withdrawn"` where no `VoiceSession` exists for that application.
4. Expose `interview_sla_hours` in `SpeakCV/src/backend/app/schemas/jobs.py` and `SpeakCV/src/backend/app/routers/jobs_hr.py`, and use `interview_window.can_apply_now` in `SpeakCV/src/backend/app/routers/public_jobs.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/vanii/Documents/Workspace/ktech/interview-path/SpeakCV/src/backend && .venv/bin/pytest tests/test_hiring_apply.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add SpeakCV/src/backend/app/hiring/ SpeakCV/src/backend/app/routers/ SpeakCV/src/backend/app/schemas/jobs.py SpeakCV/src/backend/tests/test_hiring_apply.py
git commit -m "feat: add cv_hold gate, per-application interview SLA, and unpenalized pre-interview withdraw"
```

---

### Task 4: Synchronize Manager Round (`in_manager_round`, `final_outcome`), Rejection Feedback & Talent Pool

**Files:**
- Modify: `SpeakCV/src/backend/app/hiring/decisions.py`
- Modify: `SpeakCV/src/backend/app/routers/applications.py`
- Modify: `SpeakCV/src/backend/app/bridges/brief.py`
- Modify: `SpeakCV/src/backend/app/routers/interviews.py`
- Modify: `SpeakCV/src/backend/app/posthire/talent_pool.py`
- Modify: `SpeakCV/src/backend/app/posthire/feedback.py`
- Test: `SpeakCV/src/backend/tests/test_bridges_brief.py`
- Test: `SpeakCV/src/backend/tests/test_posthire_feedback.py`

**Interfaces:**
- Consumes: `Application.hr_decision`, `Application.final_outcome`.
- Produces:
  - `decisions.visible_to_candidate(application) -> str | None`:
    - Returns `"rejected"` when `application.hr_decision == "rejected"` or `application.final_outcome == "not_hired"`.
    - Returns `"approved"` when `application.final_outcome == "hired"` or (`application.hr_decision == "approved"` and `application.final_outcome is None`).
  - `applications._out`: sets `final_outcome = application.final_outcome`, and when `application.hr_decision == "approved"` and `application.final_outcome is None`, exposes `status = "in_manager_round"` (or keeps `decision = "approved"` with `final_outcome = None` so the frontend only renders `OnboardingConsentPrompt` when `final_outcome == "hired"`).
  - `routers/interviews.py`: when `record_outcome` sets `outcome == "not_hired"`, triggers `feedback.create_draft_for(application.id)` in background tasks.
  - Direct Manager access: `routers/interviews.py` lists approved applications for the manager even if no `CandidateBrief` was sent yet when the candidate has no recorded interview (`declined_recording` / `fast_tracked`).

- [ ] **Step 1: Write the failing test**

Add tests in `SpeakCV/src/backend/tests/test_bridges_brief.py` and `SpeakCV/src/backend/tests/test_posthire_feedback.py`:
1. `test_not_hired_outcome_is_visible_as_rejected_and_eligible_for_talent_pool_and_feedback`: When HR approves (`hr_decision="approved"`) and later records `final_outcome="not_hired"`, `decisions.visible_to_candidate(app) == "rejected"`, `talent_pool.give_consent` + `opt_in` succeeds, and `feedback.create_draft_for` creates a rejection feedback draft.
2. `test_application_out_includes_final_outcome`: Verify `GET /api/applications/{id}` returns `final_outcome` (`None`, `"hired"`, `"not_hired"`).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/vanii/Documents/Workspace/ktech/interview-path/SpeakCV/src/backend && .venv/bin/pytest tests/test_bridges_brief.py tests/test_posthire_feedback.py -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

1. In `SpeakCV/src/backend/app/hiring/decisions.py`:
   ```python
   def visible_to_candidate(application) -> str | None:
       if application.stage == "ready_for_hr":
           if application.final_outcome == "not_hired":
               return "rejected"
           if application.hr_decision in DECISIONS:
               return application.hr_decision
       return None
   ```
2. In `SpeakCV/src/backend/app/routers/applications.py`:
   - Add `final_outcome: str | None = None` to `ApplicationOut` and populate `"final_outcome": application.final_outcome` in `_out()` when `decision is not None`.
3. In `SpeakCV/src/backend/app/posthire/feedback.py`:
   - Update eligibility checks where `application.hr_decision != "rejected"` is checked so that `(application.hr_decision == "rejected" or application.final_outcome == "not_hired")` is accepted.
4. In `SpeakCV/src/backend/app/routers/interviews.py`:
   - In the route that records outcome (`POST .../outcome`), accept `BackgroundTasks` and call `background.add_task(feedback.create_draft_for, application.id)` when `body.outcome == "not_hired"`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/vanii/Documents/Workspace/ktech/interview-path/SpeakCV/src/backend && .venv/bin/pytest tests/test_bridges_brief.py tests/test_posthire_feedback.py tests/test_posthire_onboarding.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add SpeakCV/src/backend/app/hiring/decisions.py SpeakCV/src/backend/app/routers/applications.py SpeakCV/src/backend/app/routers/interviews.py SpeakCV/src/backend/app/posthire/feedback.py SpeakCV/src/backend/tests/
git commit -m "feat: sync manager final_outcome with candidate status, feedback, and talent pool"
```

---

### Task 5: Passwordless Guest Apply & 1-Click Magic Link Claim (`/api/public/applications/claim`)

**Files:**
- Modify: `SpeakCV/src/backend/app/hiring/applications.py`
- Modify: `SpeakCV/src/backend/app/routers/applications.py`
- Test: `SpeakCV/src/backend/tests/test_hiring_apply.py`

**Interfaces:**
- Consumes: `security.create_access_token`, `identity.extract_contact_info`, `Application.claim_token_hash`.
- Produces:
  - `applications.issue_claim_token(db, application) -> str` (stores SHA-256 hash in `application.claim_token_hash` and returns raw URL-safe token)
  - `applications.resolve_or_create_candidate_user(db, email: str, full_name: str | None) -> User`
  - `POST /api/public/jobs/{slug}/apply`: accepts optional `candidate_email` and `candidate_name` form fields when caller is unauthenticated; extracts email/name from CV if not provided; creates/resolves `User`; returns `ApplicationOut` with optional `access_token: str | None` and `claim_token: str | None`.
  - `POST /api/public/applications/claim`: accepts `{token, consent_version, consent_language}`, verifies `claim_token_hash`, records `cv_processing` consent if not yet recorded, and returns `{application_id, access_token, token_type: "bearer"}`.

- [ ] **Step 1: Write the failing test**

Add tests in `SpeakCV/src/backend/tests/test_hiring_apply.py`:
1. `test_guest_can_apply_without_prior_login_and_receives_access_token`: Unauthenticated `POST /api/public/jobs/{slug}/apply` with a CV containing `Email: guest@example.com` creates a `User`, creates the `Application`, and returns `201` with `access_token`.
2. `test_claim_magic_link_authenticates_candidate_and_records_consent`: Calling `POST /api/public/applications/claim` with a valid `claim_token` returns a working `access_token` that can read `GET /api/applications/{id}/fit`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/vanii/Documents/Workspace/ktech/interview-path/SpeakCV/src/backend && .venv/bin/pytest tests/test_hiring_apply.py -k "guest_can_apply or claim_magic_link" -v`
Expected: FAIL (401 on unauthenticated apply, 404 on `/api/public/applications/claim`).

- [ ] **Step 3: Write minimal implementation**

1. In `SpeakCV/src/backend/app/hiring/applications.py`:
   - Add `issue_claim_token(application) -> str` using `secrets.token_urlsafe(32)` and storing `hashlib.sha256(token.encode("utf-8")).hexdigest()` in `application.claim_token_hash`.
   - Add `resolve_or_create_candidate_user(db, email: str, full_name: str | None) -> User` which finds an existing `User` case-insensitively by email or creates a new `User` with a random password hash.
2. In `SpeakCV/src/backend/app/routers/applications.py`:
   - Add optional dependency `get_optional_user` on `POST /api/public/jobs/{slug}/apply` and optional `Form(None)` fields `candidate_email` and `candidate_name`.
   - When `user is None`, extract text from the uploaded CV (`extract_cv`), run `identity.extract_contact_info(text, fallback_name=candidate_name, fallback_email=candidate_email)`, and if no email is found raise `422` asking for an email address. Otherwise resolve/create `user` via `resolve_or_create_candidate_user` and include `access_token = security.create_access_token(data={"sub": user.email})` in `ApplicationOut`.
   - Add `POST /api/public/applications/claim` and `GET /api/public/applications/claim/{token}` (returns basic job/company info + consent text so the claim page can display them before POSTing).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/vanii/Documents/Workspace/ktech/interview-path/SpeakCV/src/backend && .venv/bin/pytest tests/test_hiring_apply.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add SpeakCV/src/backend/app/hiring/applications.py SpeakCV/src/backend/app/routers/applications.py SpeakCV/src/backend/tests/test_hiring_apply.py
git commit -m "feat: add passwordless guest apply and magic-link application claiming"
```

---

### Task 6: HR Multi-Channel Bulk CV Import (`.pdf`, `.docx`, `.zip`), Cross-Channel Deduplication & Missing Contact Recovery

**Files:**
- Modify: `SpeakCV/src/backend/app/hiring/applications.py`
- Modify: `SpeakCV/src/backend/app/routers/board.py`
- Test: `SpeakCV/src/backend/tests/test_hiring_apply.py`

**Interfaces:**
- Consumes: `identity.extract_contact_info`, `applications.issue_claim_token`, `cv_processing.run`.
- Produces:
  - `POST /api/companies/{company_id}/jobs/{job_id}/import-cvs`:
    - Accepts `source_channel: str = Form("topcv")` and `files: list[UploadFile] = File(...)` (each `.pdf`, `.docx`, or `.zip` containing `.pdf`/`.docx`).
    - Deduplicates within the same `job_id` by `contact_hash` or `cv_blind_hash`: returns `{"imported": [...], "duplicates": [...], "missing_contact": [...], "errors": [...]}`.
    - If email is extracted: resolves/creates `User`, records `cv_processing` consent, issues `claim_token`, schedules `cv_processing.run`.
    - If email is missing: creates `Application` with `stage="missing_contact"` so HR can fill in email on the board.
  - `POST /api/companies/{company_id}/applications/{app_id}/contact`:
    - Accepts `{candidate_email: str, candidate_name: str | None, candidate_phone: str | None}` from HR, attaches `User`, transitions `missing_contact -> cv_processing`, and runs `cv_processing.run`.
  - `POST /api/companies/{company_id}/applications/{app_id}/invite-from-hold`:
    - Transitions `cv_hold -> invited`, sets `invited_at`, and enqueues invitation notification.

- [ ] **Step 1: Write the failing test**

Add tests in `SpeakCV/src/backend/tests/test_hiring_apply.py`:
1. `test_hr_bulk_import_cvs_and_zip_with_cross_channel_dedupe`: Upload a `.pdf` from `topcv` and a `.zip` from `itviec` containing the same candidate email + a second candidate without an email. Assert 1 `imported`, 1 `duplicates`, and 1 `missing_contact`.
2. `test_hr_can_supply_missing_contact_and_invite_from_cv_hold`: Supplying email on the `missing_contact` application processes the CV, and calling `/invite-from-hold` on a `cv_hold` application moves it to `invited`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/vanii/Documents/Workspace/ktech/interview-path/SpeakCV/src/backend && .venv/bin/pytest tests/test_hiring_apply.py -k "hr_bulk_import or missing_contact" -v`
Expected: FAIL (404 on `/import-cvs`, `/contact`, `/invite-from-hold`).

- [ ] **Step 3: Write minimal implementation**

1. In `SpeakCV/src/backend/app/hiring/applications.py`:
   - Add helper `import_cv_file(db, job, file_bytes: bytes, filename: str, source_channel: str, actor_user_id: int) -> tuple[str, Application | None, str | None]` that:
     - Validates `.pdf` / `.docx`, extracts text (`extract_cv`), extracts `ContactInfo`, and checks if an active `Application` in `job.id` already has the same `contact_hash` or SHA-256 text hash (returning `"duplicate"` if found).
     - Saves the file to storage, creates the `Application` row (`stage="submitted"` if email found, else `stage="missing_contact"`), issues `claim_token`, and if email is present resolves `User` and records `cv_processing` consent.
2. In `SpeakCV/src/backend/app/routers/board.py`:
   - Add `POST /api/companies/{company_id}/jobs/{job_id}/import-cvs` (unpacking `.zip` archives safely in memory with size/count limits, calling `import_cv_file` for each `.pdf`/`.docx`, and scheduling `cv_processing.run` for imported rows with email).
   - Add `POST /api/companies/{company_id}/applications/{app_id}/contact` and `POST /api/companies/{company_id}/applications/{app_id}/invite-from-hold`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/vanii/Documents/Workspace/ktech/interview-path/SpeakCV/src/backend && .venv/bin/pytest tests/test_hiring_apply.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add SpeakCV/src/backend/app/hiring/applications.py SpeakCV/src/backend/app/routers/board.py SpeakCV/src/backend/tests/test_hiring_apply.py
git commit -m "feat: add HR multi-channel bulk CV import, cross-channel deduplication, and contact recovery"
```

---

### Task 7: Non-Blind HR Board Read Model (`app/hiring/board.py`)

**Files:**
- Modify: `SpeakCV/src/backend/app/hiring/board.py`
- Test: `SpeakCV/src/backend/tests/test_hiring_apply.py`

**Interfaces:**
- Consumes: `Application.candidate_name`, `Application.candidate_email`, `Application.candidate_phone`, `Application.source_channel`, `Application.stage` (`cv_hold`, `missing_contact`).
- Produces:
  - `board.LANES` including `"cv_hold"` and `"missing_contact"`.
  - `board.card(application)` returning `candidate_name`, `candidate_email`, `candidate_phone`, `source_channel` alongside `alias`.
  - `board.detail(db, application, viewer_id)` returning `candidate_name`, `candidate_email`, `candidate_phone`, `source_channel`, `cv_text` (raw unmasked CV text), unmasked turn transcripts, and `identity_revealed: True` by default without requiring a prior reveal audit log.

- [ ] **Step 1: Write the failing test**

Add test `test_board_shows_real_identity_and_new_lanes` in `SpeakCV/src/backend/tests/test_hiring_apply.py`:
- Assert `board.job_board` places `cv_hold` and `missing_contact` applications in their respective lanes.
- Assert `board.card` and `board.detail` include `candidate_name`, `candidate_email`, `candidate_phone`, `source_channel`, and unmasked transcript/CV text immediately.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/vanii/Documents/Workspace/ktech/interview-path/SpeakCV/src/backend && .venv/bin/pytest tests/test_hiring_apply.py -k test_board_shows_real_identity_and_new_lanes -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

1. In `SpeakCV/src/backend/app/hiring/board.py`:
   - Add `"cv_hold"` and `"missing_contact"` to `LANES` and `_lane_for()`.
   - Include `"candidate_name"`, `"candidate_email"`, `"candidate_phone"`, `"source_channel"` in `card()` and `detail()` (falling back to `User.full_name` / `User.email` if the columns on `Application` are null).
   - Return unmasked `turn.transcript` and raw `application.cv_text_raw or application.cv_text_blind` in `detail()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/vanii/Documents/Workspace/ktech/interview-path/SpeakCV/src/backend && .venv/bin/pytest -q`
Expected: All backend tests PASS.

- [ ] **Step 5: Commit**

```bash
git add SpeakCV/src/backend/app/hiring/board.py SpeakCV/src/backend/tests/
git commit -m "feat: expose real candidate identity and cv_hold/missing_contact lanes on HR board"
```

---

### Task 8: Candidate B2C Frontend Updates (`SpeakCV/src/frontend`)

**Files:**
- Create: `SpeakCV/src/frontend/app/claim/[token]/page.tsx`
- Modify: `SpeakCV/src/frontend/services/hiring.ts`
- Modify: `SpeakCV/src/frontend/app/jobs/[slug]/page.tsx`
- Modify: `SpeakCV/src/frontend/app/applications/page.tsx`
- Modify: `SpeakCV/src/frontend/lib/i18n.ts`

**Interfaces:**
- Consumes: `POST /api/public/jobs/{slug}/apply` (passwordless support + `access_token`), `GET/POST /api/public/applications/claim`, `Application.final_outcome`.
- Produces:
  - Direct passwordless apply form on `/jobs/[slug]` (shows `AskCompanyWidget` on the job page, collects `candidate_name` & `candidate_email` when not logged in, stores returned `access_token` in `localStorage.getItem("token")`, and navigates to `/applications/{id}/fit`).
  - `/claim/[token]` page allowing candidates imported from TopCV/ITviec to review consent, claim their application in 1 click, and jump straight to `/applications/{id}/fit`.
  - `/applications` page showing manager-round status when `decision === "approved" && !final_outcome`, and rendering `<OnboardingConsentPrompt />` only when `final_outcome === "hired"`.

- [ ] **Step 1: Verify current frontend typecheck/build**

Run: `cd /home/vanii/Documents/Workspace/ktech/interview-path/SpeakCV/src/frontend && npx tsc --noEmit`

- [ ] **Step 2: Implement candidate frontend updates**

1. In `SpeakCV/src/frontend/services/hiring.ts`:
   - Add `final_outcome?: string | null` and `access_token?: string | null` to `Application`.
   - Update `applyToJob` to accept optional `candidateName` and `candidateEmail` and store `access_token` if returned.
   - Add `getClaimInfo(token: string)` and `claimApplication(token: string, consentVersion: string, consentLanguage: string)`.
2. In `SpeakCV/src/frontend/app/jobs/[slug]/page.tsx`:
   - Render `<AskCompanyWidget companySlug={job.company_slug} />` directly on the public job page.
   - Allow opening `<ApplyForm />` without requiring prior login; when `!user`, show Name and Email inputs (optional if present in CV, or prefilled).
3. Create `SpeakCV/src/frontend/app/claim/[token]/page.tsx` for 1-click Magic Link claiming.
4. In `SpeakCV/src/frontend/app/applications/page.tsx`:
   - Distinguish `a.decision === "approved" && a.final_outcome === "hired"` (shows approved/hired text + `<OnboardingConsentPrompt />`) from `a.decision === "approved" && !a.final_outcome` (shows manager-round progress text without premature `<OnboardingConsentPrompt />`).

- [ ] **Step 3: Run frontend typecheck to verify it passes**

Run: `cd /home/vanii/Documents/Workspace/ktech/interview-path/SpeakCV/src/frontend && npx tsc --noEmit`
Expected: PASS with 0 errors.

- [ ] **Step 4: Commit**

```bash
git add SpeakCV/src/frontend/
git commit -m "feat: add passwordless apply, magic-link claim page, and manager-round status in candidate app"
```

---

### Task 9: HR & Manager B2B Portal Updates (`interviewpath/interviewpath-demo`)

**Files:**
- Modify: `interviewpath/interviewpath-demo/src/lib/board.js`
- Modify: `interviewpath/interviewpath-demo/src/routes/BoardPage.jsx`
- Modify: `interviewpath/interviewpath-demo/src/components/CandidateCard.jsx`
- Modify: `interviewpath/interviewpath-demo/src/components/CandidateDetailPanel.jsx`
- Modify: `interviewpath/interviewpath-demo/src/routes/JobEditorPage.jsx`
- Modify: `interviewpath/interviewpath-demo/src/i18n/vi.json`
- Modify: `interviewpath/interviewpath-demo/src/i18n/en.json`
- Modify: `interviewpath/interviewpath-demo/src/i18n/ko.json`

**Interfaces:**
- Consumes: `POST .../import-cvs`, `POST .../contact`, `POST .../invite-from-hold`, `candidate_name`, `candidate_email`, `candidate_phone`, `source_channel`, `interview_sla_hours`.
- Produces:
  - Multi-channel Bulk CV Import bar on `BoardPage.jsx` (channel selector `topcv`, `itviec`, `linkedin`, `facebook`, `referral` + multi-file `.pdf`/`.docx`/`.zip` upload + import summary badge).
  - Real candidate name, email, phone, and source channel badge on `CandidateCard.jsx` and `CandidateDetailPanel.jsx`.
  - Action buttons in `CandidateDetailPanel.jsx` for `cv_hold` (*Invite to AI Interview*) and `missing_contact` (*Save Email & Send Magic Link*).
  - Per-application SLA hours (`interview_sla_hours`) input on `JobEditorPage.jsx`.

- [ ] **Step 1: Implement B2B portal updates**

1. In `interviewpath/interviewpath-demo/src/lib/board.js`:
   - Add `"cv_hold"` and `"missing_contact"` to `LANES`.
   - Add API helpers `importCvs(companyId, jobId, channel, files)`, `updateContact(companyId, appId, payload)`, and `inviteFromHold(companyId, appId)`.
2. In `interviewpath/interviewpath-demo/src/components/CandidateCard.jsx` and `CandidateDetailPanel.jsx`:
   - Display `card.candidate_name || card.alias`, `card.candidate_email`, `card.candidate_phone`, and `card.source_channel`.
   - In `CandidateDetailPanel.jsx`, add the inline email form when `detail.stage === 'missing_contact'` and the 1-click invite button when `detail.stage === 'cv_hold'`.
3. In `interviewpath/interviewpath-demo/src/routes/BoardPage.jsx`:
   - Add the Bulk Import CV panel at the top of the board so HR can upload `.pdf`/`.docx`/`.zip` files from TopCV/ITviec in one action.
4. In `interviewpath/interviewpath-demo/src/routes/JobEditorPage.jsx`:
   - Add `interview_sla_hours` field beside the interview scheduling window settings.

- [ ] **Step 2: Run B2B portal build & tests to verify it passes**

Run: `cd /home/vanii/Documents/Workspace/ktech/interview-path/interviewpath/interviewpath-demo && npm run build`
Expected: PASS (`vite build` succeeds cleanly).

- [ ] **Step 3: Commit**

```bash
git add interviewpath/interviewpath-demo/
git commit -m "feat: add multi-channel bulk CV import, real identity display, and cv_hold actions on HR board"
```

---

### Task 10: End-to-End Verification

**Interfaces:**
- Consumes: Updated codebase and latest `HEAD` commit.
- Produces:
  - 100% passing backend test suite and frontend builds.

- [ ] **Step 1: Run full backend test suite and frontend builds**

Run:
```bash
cd /home/vanii/Documents/Workspace/ktech/interview-path/SpeakCV/src/backend && .venv/bin/pytest -q
cd /home/vanii/Documents/Workspace/ktech/interview-path/SpeakCV/src/frontend && npx tsc --noEmit
cd /home/vanii/Documents/Workspace/ktech/interview-path/interviewpath/interviewpath-demo && npm run build
```
Expected: All pass with 0 errors.
