# SpeakCV automation surface — research findings

All paths under `/home/vanii/Documents/Workspace/ktech/interview-path/SpeakCV/src/`.

## 1. Schema (`backend/app/database/sql_models.py`)
- **InterviewHistory** (67-80): id, user_id, title, position, score, overall_feedback, details(JSON report), interview_type, question_limit, time_limit, created_at. No company/jd/voice/mode columns.
- **JDTemplate** (83-89): id, title(indexed), description, created_at. No user_id — global/admin-managed, not per-user.
- **UserProfile** (25-39): id, user_id(indexed, no FK), phone, address, website, github, linkedin, summary, skills, avatar, master_cv_text, master_cv_structured(JSON). No preferences field.
- **User** (10-22): id, email(unique, indexed), full_name, hashed_password, role, credits, plan, last_token_reset_date, must_change_password, password_changed_at. No company/preferences field.
- No table for per-user practice preferences exists today.
- `Company` (254) and `CompanyMember` (283) tables exist (hiring tenant side).
- `models.py` defines `HintRequest`/`ReportRequest`/`UserCreate` twice (57/62 and 2500/2505/2545) — second wins at import, unrelated to this feature but noted.

## 2. Alembic (`backend/alembic/versions/`)
- Linear chain, head = `0010_interview_window`: 0001_baseline...0010_interview_window.
- 0010 is additive `op.add_column` with nullable/server_default — new nullable columns follow the same safe pattern.

## 3. Auth (`backend/app/routers/auth.py`)
- `/api/register`(21), `/api/login`(37, JWT `sub=email`,48), `/api/auth/google`(78).
- Email normalized strip/lower, case-insensitive lookup via `func.lower`.
- JWT decoded in `auth/security.py:37`, resolved to user in `auth/dependencies.py:13-14`.
- Frontend stores token in sessionStorage (`services/api.ts:12`, `context/AuthContext.tsx:52`).
- No `email_verified` check found.

## 4. `/interview` page entry points (`app/interview/page.tsx`)
- Only `searchParams.get("next")` (line 86), validated by `lib/safeRedirect.ts:2-14` (same-origin only). Used as CTA link + passed to `ReportStep`.
- No other query params read anywhere in interview hooks (`useInterviewState.ts`, `useInterviewActions.ts`, `useChat.ts`).
- Browser storage on this page: `interview_context` (sessionStorage), `interview_session_state` (sessionStorage), `guest_msg_count` (localStorage). Config itself (`useInterviewState.ts:25-35`) is in-memory only, never hydrated from storage. Defaults: position/company/jd all `""`, voice `vi-VN-HoaiMyNeural`, mode `technical`, interviewType `free`, questionLimit 5, timeLimit 120.
- Existing auto-fill precedent: `page.tsx:134-143` sets position from `master_cv_structured.personal_info.title` once (ref-guarded), only if empty — this is what we just shipped.
- Other URL-param readers in the app (pattern reference):
  - `app/jobs/[slug]/page.tsx:137` reads `src`, passed to `getPublicJob`/`applyToJob`.
  - `app/login/page.tsx:25-27` reads `redirect`, round-trips via sessionStorage `postLoginRedirect` through `AuthContext.tsx:62-63`.

## 5. Relevant `services/api.ts` exports
`chatWithAI`, `endInterview`, `getHint`, `buildInterviewContext`, `getHistory`, `getHistoryDetail`, `renameInterview`, `deleteInterview`, `updateInterviewConfig(historyId, {interview_type, question_limit, time_limit})`, `getJdTemplates`(no auth header!), `createJdTemplate`, `updateJdTemplate`, `deleteJdTemplate`, `getMyProfile`, `updateProfileInfo`.
No config-get/put endpoint, no user-preferences API, no endpoint accepting an external position/company/JD push.
Backend routes (`app/routers/interview.py`): `GET/PATCH /api/history[/{id}][/config]`, `POST /api/chat`, `POST /api/end-interview`. `GET /api/templates` (`routers/admin.py:242-247`) has **no auth dependency** — anyone can read JD templates.

## 6. Cross-app linking precedent (most relevant for feature 4)
No inbound service-to-service auth exists in SpeakCV (grep for api_key/X-API-Key/service-token/HMAC found only outbound AI-provider keys + VNPAY callback HMAC + an internal `reapply_guard` HMAC). But there IS an existing **opaque-token link pattern** already built for exactly this kind of cross-boundary handoff, on the hiring side:
- `hiring/jobs.py:206`: `JobChannelLink.token = secrets.token_urlsafe(16)` minted per job per channel.
- `bridges/channels.py:75-76`: builds `/jobs/{slug}?src={token}`.
- `routers/public_jobs.py:17-27` + `hiring/applications.py:54-57`: validate `src` against DB server-side — the URL carries an opaque token, never free-text job data.
This is the template to reuse for "InterviewPath hands SpeakCV a job context safely" instead of inventing a new mechanism.
CORS: `main.py:99,123-125` uses `ALLOWED_ORIGINS` (`core/settings.py:70-76`), `allow_credentials=True` — any browser-side call from InterviewPath's origin needs to be allow-listed.

## Unknowns
- Real DB contents (not queried live by this research pass).
- How migrations run at startup (`app/database/migrate.py` not read).
- `models_hiring.py` `Job` schema not read — relevant if job context should be sourced from existing hiring jobs rather than a new table.
- Whether `PRACTICE_STEP_FLOW` changes which Setup UI reads `config` — both paths (legacy and step-flow) read the same `config` state, so no.

Risk flagged: `GET /api/templates` is unauthenticated today — JD template data is public already (pre-existing, unrelated to this feature, but relevant if JD templates get tied to companies).
