# Block 5: Measurement and Post-hire Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure which channels and requirements work, and close the loop for rejected candidates and hires: Channel Intelligence, Requirement Reality Check, Respectful Rejection, Gap-to-Growth, Talent Pool and Onboarding 30-60-90.

**Architecture:** New package `app/insights/` computes metrics by code in SQL, and `app/posthire/` handles feedback, learning, talent pool and onboarding. AI only explains computed tables and drafts text, and code verifies numbers, IDs and sources. Simulated rows are written through the real tables, and never mixed with real rows in one view.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, NumPy, React 18, Next.js 16, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-01-block-5-measurement-post-hire-design.md`, parent `docs/superpowers/specs/2026-11-01-hiring-platform-overview-design.md`.

**Execution batches, each runs in parallel:** `[1]` → `[2, 3, 4, 5, 6]` → `[7, 8, 9]` → `[10]`.

## Global Constraints

- Git commit messages: a single line, no body, never a `Co-Authored-By` trailer. Commit only the files your task touches.
- Never print, log or commit values from `.env` files. Do not push. Do not touch Docker containers you did not start.
- Routes that call the AI gateway must not block the event loop: use plain `def`, or wrap the call in `run_in_threadpool` when the route must stay `async` because of `read_upload`.
- Business code imports only `app.ai.gateway`.
- **Numbers are computed by code.** AI may explain a computed table, but may not produce figures. Every number in commentary must exist in the table.
- Requirements never change automatically. Reality Check only suggests, by a fixed rule with no AI.
- HR always approves before feedback is sent. Feedback never contains `cv_status` wording, confidential node titles, or comparisons with other candidates. A candidate with no session gets a neutral template with no AI call.
- AI may not invent course names or links. Unknown catalogue IDs are dropped. No catalogue match means no suggestion.
- Talent pool and interview-data use for onboarding each need their own consent: purposes `talent_pool` and `onboarding_use`.
- No attrition prediction and no monitoring of employee behaviour.
- `simulate-hiring` is allowed only for `is_sample=true` companies, is reproducible by seed, and makes no AI calls. Every view that includes simulated rows shows a "Simulated data" banner that cannot be dismissed. Real and simulated rows are never combined in one view.
- Every route under `/api/companies/{company_id}/...` uses `require_member`. Every schema change ships with a migration.
- `make test` needs no network and no keys. Environment per worktree: `cd SpeakCV/src/backend && uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -q -r requirements-dev.txt`.
- Read the `dataviz` skill before adding any chart.

## Review Focus

- A channel with no cost entered and zero approvals: shows "not entered" and no division by zero. Test in Task 2.
- A company with both simulated and real applications for one job: the view shows one or the other through an explicit choice, with never a blended number. Test in Task 2.
- Commentary containing "about 40%" where the table says 41.7%: rejected as an invented number. Test in Task 2.
- A rejected candidate who withdraws talent-pool consent after retention extended: the retained CV is deleted at once. Test in Task 5.
- HR triggers onboarding after retention removed interview evidence: the plan uses only the team graph, with no error. Test in Task 6.

---

### Task 1: Data model and simulator

**Files:**
- Create: `SpeakCV/src/backend/app/database/models_insights.py`, `app/insights/__init__.py`, `app/insights/simulator.py`, `alembic/versions/0008_measurement.py`, `tests/test_insights_simulator.py`
- Modify: `app/database/sql_models.py`, `app/cli.py`, root `Makefile`

**Interfaces:**
- Produces:
  - Models `ChannelCost, RejectionFeedback, LearningResource, TalentPoolEntry, OnboardingPlan, OnboardingItem, ProbationOutcome`, with spec section 1's columns
  - `simulator.simulate(db, company, seed=42, count=240) -> SimulationSummary`
  - `python -m app.cli simulate-hiring --company <slug> --seed 42`, and `make simulate-hiring`

- [ ] **Step 1: Write the failing test**

`tests/test_insights_simulator.py`, as complete tests:

1. A non-sample company raises `PermissionError`, and the CLI exits non-zero naming the rule.
2. A sample company gets rows through the real tables: applications with `is_simulated=True`, `requirement_results`, statuses, `hr_decision`, `final_outcome`, probation outcomes and channel costs.
3. **No AI call:** a spy on `gateway.generate_text` and `generate_structured` stays at zero, and `ai_usage_logs` stays empty.
4. Same seed gives identical rows; a different seed gives different rows.
5. Deliberate channel differences: the channel with the most applications is not the channel with the best `approval_rate`. The test computes this from rows directly.
6. Running twice replaces earlier simulated rows for that company, and leaves real rows alone.
7. Simulated rows contain no personal data: `cv_text_raw` and `candidate_user_id` are null, and aliases start with `#S`.
8. Requirement-level differences: one must-have is missed by many yet common among hires who passed probation, so Reality Check has a story.
9. Simulated applications never appear in the Block 3 board: `board.job_board` excludes them.

- [ ] **Step 2: Run it to verify it fails**

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

`models_insights.py` adds to the spec's columns only: `RejectionFeedback.created_at`; `TalentPoolEntry.retained_cv_text Text NULL`, because the application's blind text is anonymized on retention; `TalentPoolEntry.embedding`, `embedding_model`; `OnboardingItem.source_node_id` and `learning_resource_id` as specified; `LearningResource.skill_node_id` nullable false; `ChannelCost` unique on `(company_id, job_id, channel, period_month)`.

`simulator.simulate` uses `random.Random(seed)`, only. Channel profiles in a dict: `linkedin` high volume and low approval; `referral` low volume and high approval; `university` medium with many hidden gems; `facebook`, `topcv`, `itviec` in between. For each simulated application, draw `cv_status`, `interview_band`, stage, decision and outcome from the profile's probabilities. For each job requirement, write `RequirementResult` with `quote=None`. Costs per channel per month for 3 months in VND, with one channel left empty, so "not entered" shows. `final_outcome` for a small share, then probation outcomes for hires. `is_simulated=True` everywhere. Delete earlier simulated rows for the company first, in one transaction.

Update `board.job_board` to filter `is_simulated=False`, and add a test there.

- [ ] **Step 4: Run the tests**

Run: `make test`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add SpeakCV/src/backend Makefile
git commit -m "feat: add measurement tables and a reproducible no-AI hiring simulator for sample companies"
```

---

### Task 2: Channel Intelligence

**Files:**
- Create: `SpeakCV/src/backend/app/insights/channels.py`, `app/insights/commentary.py`, `app/routers/insights.py`, `tests/test_insights_channels.py`
- Modify: `app/main.py`, `app/brain/fake_demo.py`

**Interfaces:**
- Consumes: Block 3 models, `gateway`.
- Produces:
  - `channels.channel_table(db, company_id, job_id, simulated: bool) -> ChannelTable`, with rows of `channel, applications, cv_meets, sessions_completed, completion_rate, hr_approved, approval_rate, hidden_gems, interviews, hires, cost, cost_per_approved`, and `small_sample: bool` per row
  - `commentary.explain(table, language, company_id) -> Commentary | None`, feature `channel_commentary`, slot `bulk`; `commentary.numbers_in(text) -> set[str]`; `commentary.check_numbers(text, table) -> bool`
  - `GET .../jobs/{job_id}/channels?data=real|simulated&language=`, `POST .../channel-costs` (JSON or CSV upload), HR only. The response has `simulated: bool`, `has_real`, `has_simulated`, `table`, `commentary`, `small_sample_note`.

- [ ] **Step 1: Write the failing tests**

`tests/test_insights_channels.py`, as complete tests:

1. Hand-computed fixture: insert a small exact set of applications across two channels, and assert every column equals the hand-computed value. Include `withdrawn`, `declined_recording`, `fast_tracked` and `hidden_gem` cases.
2. Rates: `completion_rate = sessions_completed / applications`; `approval_rate = hr_approved / applications`. Zero applications gives `None`, not an exception.
3. `cost` sums matching months; a channel with no cost has `cost=None`, shown as "not entered". `cost_per_approved` is `None` with zero approved or no cost.
4. **Real and simulated never mix:** with both present, `data=real` counts only real, and `data=simulated` only simulated. The default is real when real rows exist, otherwise simulated. The response's `simulated` flag is true for simulated.
5. Talent pool is its own channel.
6. Numbers: `numbers_in("41.7% and 3 hires, about 40")` gives the three; thousands separators normalise. Commentary with a number absent from the table is rejected. `check_numbers` accepts rounded display forms only when they equal a table value at the same precision as shown in the table; "about 40%" against 41.7% fails.
7. Retry once on a failed check, then `None`, and the table still returns.
8. Any channel under 30 applications sets `small_sample`, and the code adds the statement "Sample too small, treat as a hint", regardless of the AI text.
9. AI failure returns the table with no commentary.
10. Costs: JSON upsert; CSV with columns `channel,period_month,amount_vnd`, with bad rows reported by line and nothing saved; a negative amount gets 422; `period_month` must be `YYYY-MM`.
11. Non-HR gets 403; enumeration covers these routes.

- [ ] **Step 2: Run them to verify they fail**

Expected: FAIL.

- [ ] **Step 3: Implement**

`channel_table` computes with SQL aggregates using `func.sum(case(...))`, portable across SQLite and MySQL, grouped by `source_channel`, filtered by `is_simulated`. `cv_meets` counts `cv_status='meets'`. `sessions_completed` counts stages at or after `session_completed` that had a session. `hidden_gems` counts `cv_status='not_met' AND interview_band='many'`. `hr_approved` counts `hr_decision='approved'`. `interviews` counts applications with a scorecard. `hires` counts `final_outcome='hired'`.

`commentary.explain` sends only the table as JSON in `<table>` tags, asks for short observations in the UI language, and asks it to keep numbers exactly as written. It may suggest moving effort, and never acts. `CommentaryOutput(observations: list[str])`.

Fake responder `channel_commentary`: one sentence per row citing `applications` and `approval_rate` exactly as given, prefixed `[Demo AI]`.

- [ ] **Step 4: Run the tests**

Run: `make test`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add SpeakCV/src/backend
git commit -m "feat: add Channel Intelligence with code-computed metrics and number-checked commentary"
```

---

### Task 3: Requirement Reality Check

**Files:**
- Create: `SpeakCV/src/backend/app/insights/reality_check.py`, `tests/test_insights_reality_check.py`
- Modify: `app/routers/insights.py` (if absent in your worktree, create `app/routers/reality_check.py` instead and register it; the controller reconciles), `app/main.py`, `app/database/sql_models.py` only for the settings below

**Interfaces:**
- Consumes: Block 3 and Block 4 models.
- Produces: `reality_check.report(db, company_id, job_id, simulated) -> list[RequirementRow]`, with `requirement_id, text, cv_miss_rate, hired_total, hired_with_requirement, hr_label_corrections, probation_passed_without_requirement, suggestion, too_strict_signal`; `GET .../jobs/{job_id}/reality-check?data=real|simulated`, HR only.

- [ ] **Step 1: Write the failing tests**

`tests/test_insights_reality_check.py`:

```python
@pytest.mark.parametrize("hired_total,with_req,expected", [
    (9, 0, "not_enough_data"), (10, 2, "consider_nice_to_have"), (10, 3, "review"),
    (10, 7, "review"), (10, 8, "keep"), (20, 5, "consider_nice_to_have"), (20, 6, "review"),
])
def test_rule_boundaries(hired_total, with_req, expected):
    assert reality_check.suggestion_for(hired_total, with_req) == expected
```

Plus, as complete tests: metrics on a hand-computed fixture; `hired_with_requirement` counts hires whose CV or interview result is `met` or `evidence`; `probation_passed_without_requirement` uses `probation_outcomes`; `hr_label_corrections` counts audit rows of CV-label corrections for this job; a high correction count sets `too_strict_signal` at 3 or more; thresholds are read from per-company settings; only must-haves are listed; real and simulated never mix; **no AI call** (spy at zero); requirements are unchanged after the report; the suggestion carries an action pointing to JD Studio and does nothing by itself.

- [ ] **Step 2: Run them to verify they fail**

Expected: FAIL.

- [ ] **Step 3: Implement**

`suggestion_for`:

```python
def suggestion_for(hired_total, hired_with_requirement, low_pct=30, high_pct=70, min_hired=10) -> str:
    if hired_total < min_hired:
        return "not_enough_data"
    share = hired_with_requirement / hired_total * 100
    if share < low_pct:
        return "consider_nice_to_have"
    if share <= high_pct:
        return "review"
    return "keep"
```

Per-company thresholds: add `reality_low_pct=30`, `reality_high_pct=70`, `reality_min_hired=10` to `companies` through a new migration `0009_reality_thresholds`, chained after the current head. If Task 1's `0008` is the head, use it as `down_revision`.

- [ ] **Step 4: Run the tests**

Run: `make test`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add SpeakCV/src/backend
git commit -m "feat: add Requirement Reality Check with explainable fixed-rule suggestions"
```

---

### Task 4: Respectful Rejection and Gap-to-Growth

**Files:**
- Create: `SpeakCV/src/backend/app/posthire/__init__.py`, `app/posthire/feedback.py`, `app/posthire/learning.py`, `app/routers/feedback.py`, `tests/test_posthire_feedback.py`, `tests/test_posthire_learning.py`
- Modify: `app/hiring/decisions.py`, `app/main.py`, `app/routers/applications.py`, `app/brain/fake_demo.py`, `tests/test_hiring_decisions.py`

**Interfaces:**
- Consumes: `decisions.decide`, `notify.enqueue`, models, `retriever` is not used here.
- Produces:
  - `feedback.draft(db, application, user_id) -> RejectionFeedback`, feature `rejection_feedback`, slot `bulk`; `feedback.guard(text, application) -> list[str]`; `feedback.approve(db, company_id, ids, user_id) -> int`
  - `learning.suggest(db, company_id, skill_node_ids) -> list[LearningResource]`
  - Routes: `POST .../applications/{app_id}/feedback/draft`, `GET .../applications/{app_id}/feedback`, `PATCH .../applications/{app_id}/feedback`, `POST .../feedback/approve` (single or bulk), `GET .../learning-resources`, `POST .../learning-resources` (JSON or CSV), HR only. Candidate: `GET /api/applications/{id}/feedback`, returning only approved and sent text.

- [ ] **Step 1: Write the failing tests**

`tests/test_posthire_feedback.py`, as complete tests:

1. Rejecting no longer sends the generic notification. It creates a draft, with status `draft`. Update the Block 3 test accordingly.
2. A draft from a candidate's verified results names what went well and what to build, in the candidate's language.
3. Guard: a draft containing `does not meet`, `not_met`, `không đạt`, or `미달`, a confidential node title, or a comparison with others (`other candidates`, `ứng viên khác`, `다른 지원자`) is rejected; retry once; then a template.
4. A quoted evidence phrase not in the application's verified results is rejected by the guard.
5. No session: neutral template in the candidate's language, with no AI call (spy at zero).
6. AI failure: a template that HR can edit, and status `draft`.
7. **Nothing reaches the candidate before approval.** Candidate `GET feedback` returns 404 for a draft.
8. `approve` sends through the outbox, stamping `approved_by`, `sent_at` and status `sent`. Bulk approves many. An ID of another company gets 404, with nothing changed. An HR edit is re-checked by the guard, so a `cv_status` word in an edit gets 422.
9. Approving twice is a no-op.
10. Audit row per approval, with no message body in the payload.

`tests/test_posthire_learning.py`, as complete tests:

1. Catalogue CRUD through JSON and CSV. `skill_node_id` must belong to the company. URLs must be `http` or `https`.
2. `suggest` returns catalogue rows matching skill nodes, and nothing for skills with no match.
3. The draft's prompt receives catalogue IDs. Output citing an unknown ID drops that ID, and no invented title or URL ever appears: code resolves title and URL from the row.
4. No catalogue means no learning section.

- [ ] **Step 2: Run them to verify they fail**

Expected: FAIL.

- [ ] **Step 3: Implement**

`feedback.draft` builds verified evidence: public requirement results with status and quote, and claims marked `explained`. Gaps map to skill nodes through `JobRequirement.node_id`. Output `FeedbackOutput(went_well: list[EvidencePoint], to_build: list[EvidencePoint], learning_ids: list[int], message: str)`. Code assembles the final message from the model's `message`, plus a learning list built from rows. Language comes from the application's session language, or the company default.

Change `decisions.decide`: rejection calls `feedback.create_draft_for(application)` after commit, as a background task, instead of the generic notification. Approval keeps its notification.

Candidate response adds the sent feedback text and the learning list.

Fake responder `rejection_feedback`: writes one neutral sentence with `[Demo AI]`, and one `went_well` from the first verified quote.

- [ ] **Step 4: Run the tests**

Run: `make test`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add SpeakCV/src/backend
git commit -m "feat: add HR-approved personal rejection feedback and catalogue-only learning suggestions"
```

---

### Task 5: Talent pool

**Files:**
- Create: `SpeakCV/src/backend/app/posthire/talent_pool.py`, `app/routers/talent_pool.py`, `tests/test_posthire_talent_pool.py`
- Modify: `app/hiring/consents.py`, `app/hiring/retention.py`, `app/main.py`

**Interfaces:**
- Consumes: `consents`, `gateway.embed`, `screening.assess`, `applications.create_application` internals, `retention`.
- Produces: `talent_pool.opt_in(db, application, user) -> TalentPoolEntry`, `talent_pool.leave(db, entry_id, user)`, `talent_pool.matches(db, company_id, job_id, top_k=10) -> list[TalentMatch]`, `talent_pool.invite(db, entry, job, user_id) -> Application`, `talent_pool.expire(db, now=None) -> int`. Routes: `POST /api/applications/{id}/talent-pool` (candidate, consent required), `POST /api/talent-pool/{entry_id}/leave` (candidate), `GET .../jobs/{job_id}/talent-matches` (hr), `POST .../talent-pool/{entry_id}/invite` (hr).

- [ ] **Step 1: Write the failing tests**

`tests/test_posthire_talent_pool.py`, as complete tests:

1. Opting in needs a `talent_pool` consent with the current text, stating 12 months and purpose; without it, 422. Consent text exists in `en` and `vi`.
2. `expires_at` is 12 months ahead. The blind CV is copied to `retained_cv_text`.
3. **Retention:** when the application is anonymized, audio and transcripts go, and the entry's `retained_cv_text` stays until expiry. `retention.has_extension` is unaffected for the application itself; the retained copy lives on the entry.
4. `matches` embeds retained text, ranks by cosine, re-runs the requirement assessment for the top matches through `screening.assess`-style logic against the new job, and returns alias, match strength by code, and no identity.
5. Invite creates a new application with `source_channel="talent_pool"`, a fresh session later, and earlier evidence is not reused; the candidate gets a notification. An expired or left entry gets 409. Another company's entry gets 404.
6. Leaving by the owner deletes `retained_cv_text` at once, withdraws the consent, and is idempotent. Another user gets 404.
7. `expire` deletes the retained text after `expires_at`.
8. Simulated rows are never matched.

- [ ] **Step 2: Run them to verify they fail**

Expected: FAIL.

- [ ] **Step 3: Implement**

The new-application path skips the CV upload, using the retained blind text: stage moves `submitted → cv_processing` with masking skipped, then assess, label and invite. Add `invited_from_pool` handling to `cv_processing` with a separate entry function `run_from_blind_text(application_id, blind_text)`.

Call `talent_pool.expire` in the daily task. Offer of the checkbox goes in the feedback message, added in Task 9's UI and the candidate route.

- [ ] **Step 4: Run the tests**

Run: `make test`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add SpeakCV/src/backend
git commit -m "feat: add a consent-based talent pool with expiry, leaving and re-assessment"
```

---

### Task 6: Onboarding 30-60-90

**Files:**
- Create: `SpeakCV/src/backend/app/posthire/onboarding.py`, `app/routers/onboarding.py`, `tests/test_posthire_onboarding.py`
- Modify: `app/hiring/consents.py`, `app/hiring/retention.py`, `app/main.py`, `app/brain/fake_demo.py`

**Interfaces:**
- Consumes: `retriever`, `audience.for_member`, `gateway`, `consents`, `CompanyMember`, `learning`.
- Produces: `onboarding.create_plan(db, application, user_id) -> OnboardingPlan`, feature `onboarding_plan`, slot `reasoning`; routes `POST .../applications/{app_id}/onboarding`, `GET .../onboarding/{plan_id}`, `PATCH .../onboarding/{plan_id}`, `POST .../onboarding/{plan_id}/approve`, `POST .../onboarding/items/{item_id}/done` (employee who owns it), `POST .../applications/{app_id}/probation` (manager), `POST /api/applications/{id}/onboarding-consent` (candidate), `GET .../my-onboarding` (employee).

- [ ] **Step 1: Write the failing tests**

`tests/test_posthire_onboarding.py`, as complete tests:

1. Only applications with `final_outcome="hired"` get a plan; otherwise 409.
2. Consent `onboarding_use` asked: granted means gaps are used; declined or absent means only the team graph.
3. Evidence gone after retention: only the team graph, and `used_interview_data=False`, with no error.
4. Items across phases 30, 60, 90, each referencing a real node with employee audience, or a real learning resource. Items citing an unknown ID or a confidential node are dropped by code.
5. The prompt holds no confidential text, by canary.
6. AI failure: 503, with no partial plan saved. HR can retry.
7. Manager and HR edit and approve. An employee cannot edit. Approving sets `approved_by`, status `active`, and gives the hire an `employee` membership with the job's department, creating no duplicate if one exists.
8. The hire's `my-onboarding` shows the checklist, marks items done, and can use `POST .../copilot/ask`. Another employee gets 404 for items that are not theirs.
9. Probation: the department's manager records `passed`, `failed` or `extended`, feeding Reality Check. Another department's manager gets 403.
10. No attrition or monitoring: assert models have no such fields, and that tracking stores only `done_at`.
11. The plan is unavailable to the hire before approval.

- [ ] **Step 2: Run them to verify they fail**

Expected: FAIL.

- [ ] **Step 3: Implement**

`create_plan` builds context: `role_profile`, and team nodes through an `employee` audience, plus gap text if consent and evidence exist, plus learning rows. `PlanOutput(items: list[PlanItem])` with `phase` of `30|60|90`, `title`, `source_node_id` (0 if none), `learning_resource_id` (0 if none). Code requires at least one valid reference. Fake responder `onboarding_plan`: one item per phase, citing the first context node and `[Demo AI]`.

Extend `retention.anonymize_application` nothing: plan items contain only titles built from company nodes and gaps. A gap-derived title could hold personal context, so state in the prompt: titles describe skills only.

- [ ] **Step 4: Run the tests**

Run: `make test`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add SpeakCV/src/backend
git commit -m "feat: add consented onboarding plans with checklists, Copilot access and probation results"
```

---

### Task 7: Portal: channels and Reality Check

**Files, relative to `interviewpath/interviewpath-demo`:**
- Create: `src/routes/ChannelsPage.jsx`, `src/routes/RealityCheckPage.jsx`, `src/components/SimulatedBanner.jsx`, `src/lib/insights.js`, `e2e/insights.spec.js`
- Modify: `src/App.jsx`, `src/components/Sidebar.jsx`, `src/i18n/en.json`, `src/i18n/vi.json`, `src/i18n/ko.json`, `eslint.config.js`
- Delete: `src/components/MetricCard.jsx`, if still unused

**Interfaces:**
- Consumes: Tasks 2 and 3's routes.
- Produces: `/jobs/:jobId/channels`, `/jobs/:jobId/reality-check`.

- [ ] **Step 1: Read `dataviz` skill, write the failing test**

`e2e/insights.spec.js`: with `simulate-hiring` run in `e2e/start-backend.sh` for a sample company when `E2E_SIMULATE=1`: the channel table shows sorted rows; clicking a column sorts; "Simulated data" banner is visible and has no close button; commentary shows, or the table alone when absent; "Sample too small" shows for small channels; "not entered" shows for the empty cost; the toggle between real and simulated exists only when both exist; entering a cost updates that row. Reality Check shows suggestions with "Not enough data" where it applies, and has a link to JD Studio and no apply button.

- [ ] **Step 2: Implement**

Table first. If a chart is added, it follows the `dataviz` skill. Sortable columns with `aria-sort`. `SimulatedBanner` is always rendered when the response says `simulated`.

- [ ] **Step 3: Verify**

Run: `npm run lint && npm run build && npx playwright test e2e/insights.spec.js --reporter=line`
Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add -A interviewpath/interviewpath-demo
git commit -m "feat: add Channel Intelligence and Reality Check pages with a permanent simulated banner"
```

---

### Task 8: Portal: feedback, learning and talent matches

**Files, relative to `interviewpath/interviewpath-demo`:**
- Create: `src/routes/LearningPage.jsx`, `src/components/board/FeedbackEditor.jsx`, `src/components/board/TalentMatches.jsx`, `src/lib/posthire.js`, `e2e/feedback.spec.js`
- Modify: `src/components/CandidateDetailPanel.jsx`, `src/routes/BoardPage.jsx`, `src/App.jsx`, `src/components/Sidebar.jsx`, `src/i18n/en.json`, `src/i18n/vi.json`

**Interfaces:**
- Consumes: Tasks 4 and 5's routes.
- Produces: `/learning`; the feedback editor in the detail panel; talent matches on the board. `src/lib/posthire.js`, used by Task 9.

- [ ] **Step 1: Write the failing test**

`e2e/feedback.spec.js`: HR rejects on the board; the draft appears with a `Demo AI` notice; HR edits, adds the forbidden phrase, and sees an error; removes it and approves; bulk approval for several works. The learning catalogue accepts a row, and rejects a bad URL. Talent matches list aliases only, and invite creates an application.

- [ ] **Step 2: Implement**

Board cells that are rejected show a "feedback pending" count. `FeedbackEditor` shows the message, what went well, what to build, and learning links, each from verified sources.

- [ ] **Step 3: Verify**

Run: `npm run lint && npm run build && npx playwright test e2e/feedback.spec.js --reporter=line`
Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add -A interviewpath/interviewpath-demo
git commit -m "feat: add feedback approval, learning catalogue and talent matches to the portal"
```

---

### Task 9: Onboarding UI and candidate app changes

**Files:**
- Create, in the portal: `src/routes/OnboardingPage.jsx`, `src/routes/MyOnboardingPage.jsx`, `src/components/board/ProbationControl.jsx`, `e2e/onboarding.spec.js`
- Modify, in the portal: `src/App.jsx`, `src/components/Sidebar.jsx`, `src/components/CandidateDetailPanel.jsx`, `src/i18n/*.json`, `src/lib/posthire.js`
- Modify, in the candidate app `SpeakCV/src/frontend`: `app/applications/page.tsx`, `app/my-data/page.tsx`, `services/hiring.ts`, `lib/i18n.ts`

**Interfaces:**
- Consumes: Tasks 4, 5, 6's routes. If `src/lib/posthire.js` is absent in your worktree, add the functions you need; the controller merges.
- Produces: `/onboarding/:planId`, `/my-onboarding`. Candidate: feedback view with the "keep my profile for 12 months" checkbox, a learning list, a re-apply date, an onboarding-consent prompt, and Leave talent pool.

- [ ] **Step 1: Write the failing test**

`e2e/onboarding.spec.js`: HR records `hired`; generates a plan; items show in 30, 60, 90 columns with their source; manager edits; HR approves. The hire signs in on the portal as an employee, sees the checklist, marks one item done, and asks Copilot. The manager records probation.

Candidate pages are covered by Task 10's end-to-end test.

- [ ] **Step 2: Implement**

The candidate's feedback view never shows internal wording. Extend `tests/test_no_fake_claims_frontend.py`'s scan if new folders were added. Withdrawing talent-pool consent is one click in My data with a confirmation stating that the retained CV is deleted now.

- [ ] **Step 3: Verify**

Run: `npm run lint && npm run build && npx playwright test e2e/onboarding.spec.js --reporter=line` in the portal, and `npm run lint 2>&1 | tail -3 && NEXT_PUBLIC_API_URL=http://localhost:8001 npm run build 2>&1 | tail -3` in the candidate app.
Expected: pass, with no new lint errors.

- [ ] **Step 4: Commit**

```bash
git add -A interviewpath/interviewpath-demo SpeakCV/src/frontend
git commit -m "feat: add onboarding pages, probation, and feedback with talent pool for candidates"
```

---

### Task 10: Block end-to-end tests

**Files:**
- Create: `interviewpath/interviewpath-demo/e2e/posthire-loop.spec.js`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Write and run the tests**

Path A, per spec: apply, interview, HR rejects with feedback, HR approves it, and the candidate reads it with no internal wording, ticks talent pool, and later leaves.

Path B: apply, approve, brief, scorecard, hired, onboarding approved, and the hire uses the checklist and Copilot.

Run: `npx playwright test e2e/posthire-loop.spec.js --reporter=line`, twice.
Expected: pass both times.

- [ ] **Step 2: Commit**

```bash
git add interviewpath/interviewpath-demo/e2e
git commit -m "test: add post-hire end-to-end paths for rejection feedback and onboarding"
```

---

## Block acceptance (controller, after Task 10)

Spec section 11:

1. Channel figures match fixtures: `tests/test_insights_channels.py`.
2. Commentary cannot show an absent number: same file.
3. Simulated banner: `e2e/insights.spec.js`.
4. Reality Check rules: `tests/test_insights_reality_check.py`.
5. Rejected candidates get only approved feedback, with no forbidden wording: `tests/test_posthire_feedback.py`, `e2e/posthire-loop.spec.js`.
6. Learning links only from the catalogue: `tests/test_posthire_learning.py`.
7. Own consents: `tests/test_posthire_talent_pool.py`, `tests/test_posthire_onboarding.py`.
8. A hire gets a plan, checklist and Copilot: `e2e/posthire-loop.spec.js`.

Run `make test`, migration on throwaway MySQL, and dispatch the final whole-branch review on `worker-opus`. Then run the complete Playwright suite once across all blocks.
