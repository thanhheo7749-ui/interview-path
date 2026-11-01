# Block 1: Foundation Design

Parent: [Product Overview](2026-11-01-hiring-platform-overview-design.md). Depends on nothing.

## Goal

Make the system safe and honest, make AI vendors swappable, and add the company concept. After this block the HR portal has a real login and manages real companies, departments and members.

## 1. Preserve the mockup

Before any cleanup, tag the current `main` as `mockup-2026-11` so the pitch-era demo stays reachable. Leave the `deploy` branch untouched until Block 3 is done.

## 2. Secrets and repository cleanup

Findings verified on 2026-11-01: `.env` and `SpeakCV/.env` are tracked and hold real values; 1,019 tracked files sit under `SpeakCV/.claude/worktrees/`; 8 SQL dumps are tracked. The repository is private.

- Remove from tracking, keeping local copies: `.env`, `SpeakCV/.env`, `SpeakCV/.claude/worktrees/`, all tracked `*.sql` dumps.
- Update `.gitignore`: `.env`, `.env.*`, `!.env.example`, `.claude/worktrees/`, `.superpowers/`, `.playwright-mcp/`, `*.sql`.
- Add a root `.env.example` listing every variable with no real values.
- **Do not rewrite history.** The repository is private and the exposed values get rotated. If it ever goes public or to the organiser, publish from a new repository, because dumps remain in history.
- `scripts/sync-vps-env.sh` reads `SpeakCV/.env` and writes `.env`, and `scripts/vps-deploy.sh` reads `.env`. Keep them working with untracked files, and document the backup step for the VPS.

## 3. Close security holes

| Issue | Change |
|---|---|
| Admin credentials in `interviewpath-demo/src/components/Sidebar.jsx` link | Delete the link and its credentials; remove query-string prefill from `SpeakCV/src/frontend/app/login/page.tsx` |
| Fallback signing key in `app/auth/security.py` | `SECRET_KEY` is required; startup fails with a clear message if missing or shorter than 32 characters |
| Default credentials in compose files, `database.py`, `main.py` | No defaults. Compose reads `env_file`. Local development uses `.env` from `.env.example` |
| `seed_admin` resets the admin password on every boot | Create only if absent; never overwrite |
| Google token audience unchecked in `routers/auth.py` | Verify audience against `GOOGLE_CLIENT_ID` |
| AI routes without authentication | Require login on every route that calls AI |
| Upload filename unsanitised in `routers/interview.py`; no size limits | Generated filenames only; `MAX_UPLOAD_MB`, default 20 |
| No rate limiting | `slowapi` on login and register; available for later public routes |
| Open CORS configuration | `ALLOWED_ORIGINS` env var, explicit list |

## 4. Legacy consumer features behind a flag

The new workflow has no place for these, and some are unsafe. They stay in the repository but are disabled by default.

- `LEGACY_B2C_ENABLED` (default `false`) controls whether `main.py` mounts `payment`, `support`, `jobs`, `stats`, `questions` and the legacy `interview` routers, plus the legacy brain endpoints in `admin`.
- `NEXT_PUBLIC_LEGACY_B2C_ENABLED` hides the matching pages and widgets in the candidate app: `/interview`, `/dashboard`, `/questions`, checkout, credits, support chat, job match and CV builder.
- The unauthenticated support chat and `/api/upgrade-pro` stay off with the flag, and are not reachable when it is false. A test asserts this.

Nothing is deleted in this block except the fake items below.

## 5. Remove fake claims

Delete, do not hide:

- `ENTERPRISE_DEMO_PRESETS`, the fixed-78% CV-JD panel: `components/Interview/SetupForm.tsx`, `InterviewLayout.tsx`
- `DEMO_SAMPLE_ANSWERS`: `components/Interview/ChatBox.tsx`
- The hardcoded 8.6 "Instant HR & Coaching Report": `app/interview/page.tsx`, `InterviewLayout.tsx`
- "PII Masked" badges: `SetupForm.tsx`, `InterviewLayout.tsx`, `PlannerSignals.tsx`, `ReportModal.tsx`
- `pii_anonymized`, `evidence_grounded` and the minutes-saved formula: `services/interview_report_builder.py`, `ReportModal.tsx`, `app/interview/page.tsx`, and their tests
- `MOCK_JOBS`: `routers/jobs.py`
- Static testimonials: `app/page.tsx`
- The `/api/cv/parse-master-cv` bug in `routers/cv.py`: the route runs `json.loads` on raw CV text. Delete the route, its frontend callers and `tests/test_cv_parse_master_cv_route.py`. Block 3's CV processing replaces it.
- `core/knowledge_graph.py` and its use in `routers/interview.py`, then drop `networkx` if unused.

In `interviewpath-demo`, delete `routes/N8nWorkflowPage.jsx`, `routes/InterviewPage.jsx`, `components/n8n/`, `components/InterviewRoom.jsx`, `components/CameraPreview.jsx`, `data/mockN8nWorkflow.js`, `data/mockInterview.js`. Remove `WorkflowPage` and `KnowledgeGraphPage` from the routes and menu; their components stay until Blocks 2 and 3 connect them to real data. No page shows mock data.

## 6. AI Gateway

### Interface

New package `SpeakCV/src/backend/app/ai/`:

```
app/ai/
  gateway.py      public functions below
  config.py       reads env vars into slot settings
  types.py        results, usage, error classes
  pricing.yaml    prices per model, with an as_of date
  providers/      anthropic.py, openai.py, gemini.py, voyage.py, edge_tts.py, fake.py
```

```python
def generate_text(slot, system, messages, max_output_tokens, feature, company_id=None) -> TextResult
def generate_structured(slot, system, messages, schema, max_output_tokens, feature, company_id=None) -> StructuredResult
def embed(texts, kind, feature, company_id=None) -> EmbeddingResult   # kind: "query" or "document"
def transcribe(audio, mime_type, languages, feature, company_id=None) -> TranscriptResult
def synthesize(text, language, voice, feature, company_id=None) -> AudioResult
```

`slot` is `"reasoning"` or `"bulk"`. `schema` is a Pydantic model. `EmbeddingResult` carries the model name and dimension.

### Configuration

```
AI_REASONING_PROVIDER, AI_REASONING_MODEL
AI_BULK_PROVIDER, AI_BULK_MODEL
AI_EMBEDDING_PROVIDER, AI_EMBEDDING_MODEL, AI_EMBEDDING_DIM
AI_STT_PROVIDER, AI_STT_MODEL
AI_TTS_PROVIDER, AI_TTS_MODEL
ANTHROPIC_API_KEY, OPENAI_API_KEY, OPENAI_BASE_URL, GEMINI_API_KEY, VOYAGE_API_KEY
```

Starting the app fails clearly if a configured slot has no key. Default `OPENAI_BASE_URL` is the official endpoint.

`.env.example` sets every slot to `fake`, so the app runs with no keys. `APP_ENV=production` refuses to start with any `fake` slot. Choosing vendors is the owner's decision and is not fixed by this spec. When the owner chooses Anthropic, the defaults are `claude-opus-5-5` for `reasoning` and `claude-haiku-5-5` for `bulk`; `claude-sonnet-5-5` is the cheaper `reasoning` option if the owner wants it.

### Rules

- Business code imports only `app.ai.gateway`. A test fails if vendor SDKs are imported elsewhere.
- Use only what all vendors share. Never send `temperature` or `top_p`; Claude rejects them. Send JSON schemas using only objects, arrays, strings, numbers, booleans, enums and `required`, with `additionalProperties: false`. Enforce other constraints in Pydantic after the response.
- `generate_structured` validates the response and retries once with the validation error. A second failure raises `AIOutputError`.
- No automatic cross-vendor failover, because vendors have different data commitments.
- `fake` provider: deterministic, offline, used by all tests.
- Each call writes one row to `ai_usage_logs`: time, company, feature, slot, provider, model, input and output tokens, audio seconds, characters, latency, estimated cost, success. This is how real cost per session is measured for the Feasibility slide.

### Vendor adapters

Use each vendor's official SDK, never an OpenAI-compatible shim for another vendor. Implementers must read current vendor docs first.

- **Anthropic**: the implementer reads the `claude-api` skill. Use `client.messages.parse()` for structured output. Handle `stop_reason == "refusal"` before reading content. Do not send a disabled-thinking setting. Set `output_config.effort` explicitly. Enable server-side `fallbacks` by default where the skill calls for it, for Opus and Sonnet.
- **OpenAI**: read the structured-outputs guide before coding, since this spec's research did not confirm its current Python shape. For STT use `gpt-transcribe`; older transcribe models shut down on 2027-02-26. It takes a `languages` array.
- **Gemini**: `google-genai` replaces the deprecated `google-generativeai`. The docs show `client.interactions.create` with `response_format`.
- **Voyage**: for embeddings when Claude handles text. Pass `input_type` from `kind`.
- **edge-tts**: the existing default for TTS. Unofficial; see the overview risks.

### Vendor facts as read on 2026-11-01

Recheck before relying on these.

| Capability | Anthropic | OpenAI | Gemini |
|---|---|---|---|
| reasoning, USD per 1M in/out | `claude-opus-5-5` 4/20, `claude-sonnet-5-5` 2/10 | `gpt-6-astra` 10/50 | `gemini-3.8-flash` 0.75/3.75, doubling on 2027-01-01 |
| bulk | `claude-haiku-5-5` 0.10/0.50, prompts up to 100K tokens | `gpt-6-luna` 0.10/0.50 | `gemini-3.5-flash-lite` 0.30/2.50 |
| embedding | None; docs point to Voyage AI | `text-embedding-3-small` 0.02, `-3-large` 0.13 | `gemini-embedding-2` 0.20 |
| stt | Not on pricing page | `gpt-transcribe` | Text models accept audio, 32 tokens/second |
| tts | Not on pricing page | `gpt-4o-mini-tts` | `gemini-3.8-flash-tts` |
| Trains on API data by default | No | No; logs kept up to 30 days | Paid no, **free tier yes** |

Why this matters: `gemini-2.0-flash`, hardcoded in `app/ai_service.py`, shut down on 2026-06-01, and the repository holds no real Gemini key, so by configuration all AI calls today go through an unofficial proxy. This was read from configuration and not observed at runtime.

Rough cost per session, **unmeasured**, assuming 10 turns, 45,000 input tokens, 5,000 output tokens, 15 minutes of audio, free TTS, no caching or reasoning tokens. OpenAI STT uses the older model's price because `gpt-transcribe` pricing was not looked up.

| Stack | Keys | USD per session |
|---|---|---|
| Gemini only | 1 | about 0.06 (0.12 from 2027) |
| Claude and OpenAI | 2 | Sonnet about 0.19, Opus about 0.33 |
| OpenAI only, flagship | 1 | about 0.75 |

### Legacy module

`app/ai_service.py` keeps `call_ai_chat`, `call_ai_chat_with_meta` and `call_ai_chat_stream` for `routers/jobs.py`, `admin.py`, `cv.py` and `interview.py`, but delegates to the gateway. Remove the hardcoded model map, the Gemini SDK import, and the proxy reference. `routers/interview.py` calls `gateway.synthesize` instead of importing `edge_tts`.

## 7. Database migrations

Introduce Alembic in `SpeakCV/src/backend`. The first revision is a baseline of the current schema. Existing databases are stamped, losing no data. Remove `create_all` and the hand-written `ALTER` code from `main.py`. The container runs `alembic upgrade head` on start.

## 8. Companies and roles

```
companies          id, slug (unique), name, is_sample, default_locale, retention_days=90,
                   kb_version=0, created_at
departments        id, company_id, parent_id NULL, name, created_at
                   unique (company_id, parent_id, name)
company_members    id, company_id, user_id, department_id NULL, role, created_at
                   unique (company_id, user_id); role in hr, manager, employee
ai_usage_logs      as in section 6
```

`departments.parent_id` models both departments and teams. A candidate is a user with no membership, which lets one person apply to both sample companies. `users.role` keeps `user` and `admin`; platform `admin` has no implicit access to company content.

### Authorization

All company APIs live under `/api/companies/{company_id}/...` and use a `require_member(roles=...)` dependency that loads the membership from the database on each request, so revocation is immediate. Non-members get 403.

### Endpoints

```
GET    /api/me                                     user and memberships
GET    /api/companies/{id}                         any member
PATCH  /api/companies/{id}                         hr
GET    /api/companies/{id}/departments             any member
POST   /api/companies/{id}/departments             hr
PATCH  /api/companies/{id}/departments/{dept_id}   hr
DELETE /api/companies/{id}/departments/{dept_id}   hr, 409 if not empty
GET    /api/companies/{id}/members                 hr
POST   /api/companies/{id}/members                 hr
PATCH  /api/companies/{id}/members/{member_id}     hr
DELETE /api/companies/{id}/members/{member_id}     hr
```

Companies are created by a CLI, `python -m app.cli create-company`, which also creates the first HR user. No platform admin UI is built.

## 9. HR portal

`interviewpath/interviewpath-demo` keeps its folder name in this block.

- API client with the base URL from `VITE_API_URL`, attaching the Bearer token and redirecting to login on 401.
- `AuthContext` with the token in `sessionStorage`, matching SpeakCV. Domains differ, so cross-site cookies are avoided.
- Login page and route guard using the backend's login endpoint.
- Company settings page: departments as a tree, members with roles.
- Banner "Sample data" whenever `company.is_sample` is true.
- i18n scaffolding with `react-i18next`: English default, Vietnamese second. Korean arrives in Block 4.

## 10. Error handling

- Missing configuration fails at startup with the variable name.
- AI errors surface as `AIProviderError` (transient, HTTP 503 to clients) or `AIOutputError` (HTTP 502). Never swallow them into fake content.
- Reject oversized uploads with 413 and unsupported types with 415.

## 11. Testing

`make test` runs `pytest` from `requirements-dev.txt`, which adds `pytest` and `httpx`. Tests use SQLite where compatible and the `fake` AI provider, and need no network.

Required tests:

- **Route-enumeration isolation test**: walk `app.routes`; every path under `/api/companies/{id}` must return 403 for a member of another company. New routes are covered automatically.
- Role matrix for company endpoints.
- Startup fails without `SECRET_KEY`.
- With the flag off, legacy routes return 404.
- Only `app/ai/` imports vendor SDKs.
- Gateway: structured retry, usage logging, missing key.
- Replace existing tests that assert removed fake fields.

Frontend: lint and a Playwright smoke test for portal login.

## 12. Acceptance criteria

1. `git ls-files` shows no `.env` with secrets, no worktree copies, no `.sql` dumps.
2. App refuses to start without `SECRET_KEY`.
3. An HR user of company A gets 403 calling company B, proven by the enumeration test.
4. An HR user logs into the portal and manages departments and members in the real database.
5. A grep for each removed fake identifier finds nothing in active code.
6. Switching a slot's provider needs only env var changes; `fake` passes all tests.
7. `make test` passes.

## 13. Out of scope

Knowledge graph (Block 2), jobs and applications (Block 3), CI pipelines, renaming `interviewpath-demo`, deleting legacy B2C code.
