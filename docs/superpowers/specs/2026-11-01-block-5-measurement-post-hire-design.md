# Block 5: Measurement and Post-hire Design

Parent: [Product Overview](2026-11-01-hiring-platform-overview-design.md). Depends on [Block 3](2026-11-01-block-3-hiring-loop-design.md) and [Block 4](2026-11-01-block-4-bridges-design.md).

## Goal

Measure which channels and requirements work (contest idea 3, #9), and close the loop for rejected candidates (#12, #11) and hires (#10).

**Honesty constraint:** Channel Intelligence and Reality Check need months of real hiring data. On sample companies they run on labelled simulated data and prove the mechanism, not the effect. Slides must say so.

## 1. Data model

```
channel_costs       id, company_id, job_id NULL, channel, period_month, amount_vnd, source (manual|csv)
rejection_feedbacks id, company_id, application_id, language, draft, status (draft|approved|sent),
                    approved_by NULL, sent_at NULL
learning_resources  id, company_id, skill_node_id, title, url, provider, language, created_by
talent_pool_entries id, company_id, candidate_user_id, source_application_id, consent_id, expires_at, status
onboarding_plans    id, company_id, application_id, employee_user_id, used_interview_data,
                    status (draft|approved|active|done), approved_by NULL
onboarding_items    id, plan_id, phase (30|60|90), title, source_node_id NULL, learning_resource_id NULL,
                    owner_user_id NULL, done_at NULL
probation_outcomes  id, company_id, application_id, result (passed|failed|extended), recorded_by, recorded_at
```

Block 3's `applications.is_simulated` marks simulated rows.

## 2. Simulator

`python -m app.cli simulate-hiring --company <slug> --seed 42` writes rows through the real tables with **no AI calls**, covering applications, statuses, results, outcomes and costs, with deliberate differences between channels so the demo tells a story. It is allowed only for `is_sample=true` companies, and is reproducible by seed.

Any dashboard including simulated rows shows a **"Simulated data"** banner, which cannot be dismissed. Real and simulated rows are never combined in one view.

## 3. Channel Intelligence (contest idea 3)

The primary measure is **which channels produce people HR approves, and at what cost**, not application count.

### Metrics

Computed by code, in SQL, per job and channel:

```
applications, cv_meets, sessions_completed, completion_rate,
hr_approved, approval_rate, hidden_gems, interviews, hires, cost, cost_per_approved
```

`completion_rate` also monitors the risk that an AI-first gate drives candidates away.

Attribution is last touch: the channel link used to apply. Talent pool is its own channel.

### Costs

HR enters cost per channel and month, or imports a CSV with columns `channel, period_month, amount_vnd`. A channel with no cost shows "not entered".

### AI commentary

`generate_structured` on `bulk` receives only the computed table and writes short observations in the UI language.

- **Every number in the commentary must exist in the table.** Code extracts numbers from the text and checks them. On failure it retries once, then shows the table with no commentary.
- Any channel with fewer than 30 applications triggers a "sample too small, treat as a hint" statement, added by code.
- It may suggest moving effort between channels; it never moves money or acts.

A free-form "ask the dashboard" chat is out of scope.

### UI

Portal page per job: table with sortable columns, AI commentary, simulated banner. Implementers must read the `dataviz` skill before adding any chart. Delete `MetricCard` demo values if still unused.

## 4. Requirement Reality Check (#9)

Per must-have requirement, computed by code:

```
cv_miss_rate, hired_total, hired_with_requirement, hr_label_corrections,
probation_passed_without_requirement
```

Suggestion by **fixed rule**, no AI, so it is explainable:

| Condition | Suggestion |
|---|---|
| `hired_total` under 10 | Not enough data |
| Hired with requirement under 30% | Consider changing to "nice to have" |
| Hired with requirement 30% to 70% | Review |
| Otherwise | Keep |

Thresholds are initial values, set per company. It only suggests; HR acts by opening JD Studio. Requirements never change automatically.

A high count of HR label corrections on a requirement is highlighted as a sign the CV criterion is too strict.

## 5. Respectful Rejection (#12)

When HR rejects, the system drafts a personal message, in the candidate's language, from verified evidence: what went well, what to build for this role, and suggested learning.

Rules enforced by code after generation:

- The draft must not contain `cv_status` wording, confidential node titles, or comparisons with other candidates.
- Any named evidence must come from the application's verified results.
- A candidate with no session receives a neutral template with no AI call.

**HR always approves before sending**, with bulk approval available. Delivery goes through the Block 3 outbox. If AI drafting fails, HR sees a template to edit.

This replaces Block 3's generic rejection notification.

## 6. Gap-to-Growth (#11)

`learning_resources` is a catalogue that the company enters or imports. Suggestions map a gap's skill node to catalogue rows.

**AI may not invent course names or links**: the prompt receives catalogue IDs, code resolves them, and unknown IDs are dropped. No catalogue match means no suggestion.

Candidates may re-apply under the Block 3 rule, creating a new application and session. Earlier evidence is not reused.

K-Tech College's train-then-match model fits this feature, so slides may name it as a possible deployment path but must not imply a partnership.

## 7. Talent pool

The feedback message offers a checkbox: keep my profile for 12 months. This is a **separate consent** with purpose `talent_pool`.

On a new job, code matches pool entries using embeddings over the blind CV, then re-runs the requirement assessment for the top matches. HR sees "past applicants who may fit" and decides whether to invite. An invitation creates a new application with `source_channel=talent_pool` and a new session.

This consent extends retention of the blind CV only, until the entry ends. Audio and transcripts still follow the Block 3 retention rule. Entries expire automatically, and candidates can leave at any time, which deletes the retained CV.

## 8. Onboarding 30-60-90 (#10)

Trigger: HR sets `final_outcome=hired`.

1. The candidate is asked for separate consent, purpose `onboarding_use`, to use interview gaps. If declined, the plan uses only the team graph. HR must trigger the plan before the Block 3 retention task removes the evidence; if it is gone, the plan uses only the team graph.
2. `generate_structured` on `reasoning` builds items across 30, 60 and 90 days from the team's graph nodes, with audience `employee`, and from gaps if consented. Each item must reference a real node or learning resource, verified by code.
3. Manager and HR edit, then approve.
4. The hire receives an `employee` membership, sees the plan as a checklist, and can use Policy Copilot.
5. The manager records a probation result in `probation_outcomes`, which feeds Reality Check.

No attrition prediction and no monitoring of employee behaviour.

## 9. API

```
GET  /api/companies/{id}/jobs/{job_id}/channels
POST /api/companies/{id}/channel-costs            manual or CSV
GET  /api/companies/{id}/jobs/{job_id}/reality-check
POST /api/companies/{id}/applications/{app_id}/feedback/draft
POST /api/companies/{id}/feedback/approve         single or bulk
GET  /api/companies/{id}/learning-resources
POST /api/companies/{id}/learning-resources       manual or CSV
GET  /api/companies/{id}/jobs/{job_id}/talent-matches
POST /api/companies/{id}/talent-pool/{entry_id}/invite
POST /api/talent-pool/{entry_id}/leave            candidate
POST /api/companies/{id}/applications/{app_id}/onboarding
PATCH /api/companies/{id}/onboarding/{plan_id}
POST /api/companies/{id}/onboarding/{plan_id}/approve
POST /api/companies/{id}/onboarding/items/{item_id}/done   employee
POST /api/companies/{id}/applications/{app_id}/probation   manager
```

## 10. Testing

`fake` provider tests:

- Metric SQL on fixed fixtures, with hand-computed expected values.
- Number check rejects invented figures.
- Small sample statement appears.
- Reality Check rule boundaries.
- Rejection draft guard against label and confidential wording.
- Unknown learning resource IDs dropped.
- Consent required for pool and for onboarding data use.
- Pool expiry.
- Simulator refuses non-sample companies; banner shown whenever simulated rows are included.
- Simulated rows never mix with real rows.

Playwright: reject with feedback, then hire through onboarding checklist.

## 11. Acceptance criteria

1. Channel table figures match hand-computed fixtures.
2. AI commentary cannot show a number absent from the table.
3. Every view containing simulated rows shows the banner.
4. Reality Check suggestions follow the rule and say "not enough data" under the minimum.
5. A rejected candidate receives only HR-approved feedback, without the "does not meet" wording or confidential criteria.
6. Learning suggestions only ever link to catalogue entries.
7. Talent pool and interview-data use require their own consents.
8. A hired candidate gets an approved plan, a checklist and Copilot access.

## 12. Out of scope

Attribution beyond last touch, ad platform integrations, free-form dashboard chat, attrition prediction, employee monitoring.
