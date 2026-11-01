# Block 4: Bridges Design

Parent: [Product Overview](2026-11-01-hiring-platform-overview-design.md). Depends on [Block 2](2026-11-01-block-2-company-brain-design.md) and [Block 3](2026-11-01-block-3-hiring-loop-design.md).

## Goal

Bridge the gap between Korean managers, Vietnamese HR and candidates: capture requirements from the manager (#1), produce recruiting content (contest idea 2), and give the manager a Korean brief and scorecard (#6).

## Flow

```
HR opens request → Manager Intake → HR approves knowledge → JD Studio → Manager approves Korean version → HR publishes, posts by channel link
```

## 1. Data model

```
hiring_requests     id, company_id, department_id, title, manager_user_id, status, created_by, created_at
job_drafts          id, company_id, hiring_request_id NULL, job_id NULL, version, lines JSON,
                    lint JSON, status (draft|manager_review|approved|published), approved_by NULL, created_at
channel_contents    id, company_id, job_draft_id, channel, language, body, link_id NULL, created_at
candidate_briefs    id, company_id, application_id, language, content JSON, status (draft|sent),
                    reviewed_by NULL, sent_at NULL
interview_scorecards id, company_id, application_id, manager_user_id, requirement_scores JSON,
                    recommendation (hire|no_hire), notes, submitted_at
```

`job_drafts.lines` holds structured lines for each language:

```json
{"id": "l1", "text": {"en": "...", "vi": "...", "ko": "..."},
 "source_node_ids": [12], "hr_confirmed": null}
```

Generating all languages from one line structure keeps the facts identical across languages.

## 2. Manager Intake (#1)

Reuses the `voice_sessions` engine from Block 3 with `purpose=intake`. The person interviewed is the manager, in Korean by default.

- **Length**: 5 to 7 minutes.
- **Plan**: the AI reads the graph first with HR audience and asks only about what is missing. Topics:
  1. Why this hire, and the work in the first 6 months.
  2. What the best person on the team does differently.
  3. A past hire that did not work out, and why.
  4. What cannot be compromised.
  5. What can be taught after joining.
  6. How the team works and reports.
- **Personal data**: the AI asks the manager not to name individuals. Names that appear are masked before storage as nodes.
- **Output**: the transcript becomes a `kb_documents` row with `source_type=intake`, `visibility=confidential`, and goes through the **same Block 2 pipeline**, including quote verification and HR review. HR picks the layer per item. Citations point to transcript moments.

### Discrimination guard

Extracted requirement candidates pass a classifier for age, gender, marital status or pregnancy, appearance, region, religion and ethnicity. A flagged item is **blocked from becoming a requirement**, shown to HR with the reason, and HR may only reject it or rewrite it as a job-related skill. This is a Q&A demo moment: "preferably under 30" does not enter the system.

### Manager pages

Portal adds Korean i18n for manager-facing pages: intake, JD approval, brief, scorecard.

## 3. JD Studio (contest idea 2)

The recruiting content assistant has three parts.

### 3.1 Job description

`generate_structured` on `reasoning`, using `search` and `role_profile` with **candidate audience**, so confidential content cannot leak by construction. Output is the line structure above, in Vietnamese, English and Korean. Each line traces to source nodes. Code verifies that `source_node_ids` exist in the context.

### 3.2 Recruiting content per channel

| Channel | Content |
|---|---|
| LinkedIn | Professional post on projects and how the team works |
| Facebook group | Short, friendly, Vietnamese |
| ITviec, TopCV | Fills those sites' job-post sections |
| University | Email to a faculty, and a post for final-year students |

Each piece includes its tracked channel link from Block 3. HR copies and posts by hand; **the system does not post to job boards**.

### 3.3 Conversational editing

```
POST /api/companies/{id}/job-drafts/{draft_id}/assistant   { "message": "..." }
```

HR can ask, for example, "make it shorter and friendlier for final-year students". The response is a revised draft and a change summary.

Rules:

- **AI cannot add salary, benefits or requirements absent from the graph.** A line with no valid source is rejected by code. The assistant instead asks HR to confirm; a confirmed line records `hr_confirmed` with user and time, and is labelled "Confirmed by HR".
- Every revision re-runs lint.
- Conversation history is kept per draft.

### 3.4 Lint

Runs on every revision:

| Check | Method | Severity |
|---|---|---|
| Discrimination: age, gender, appearance, region and similar | Rules plus AI classifier | Blocks publish |
| Conflicts with the graph, e.g. JD says flexible, policy says 9:00–18:00 | Reuses Block 2 contradiction logic | Blocks until resolved or marked as different scope |
| More than 6 must-have requirements | Code | Warning |
| Line without a source | Code | Blocks |

### 3.5 Approval and publishing

HR edits → manager approves the Korean version → HR publishes. Publishing creates or updates the Block 3 `jobs` row, requirements from nodes, and increases `job.version`, which invalidates cached CV results for new applications.

## 4. Korean Bridge and Interview Kit (#6)

Generated after HR approves an application, from structured evidence, not free recall. Language is the manager's locale, Korean by default.

Content, fixed structure:

- Confirmed strengths
- Items to clarify
- Up to 5 interview questions aimed at unclear items and the team's requirements
- For each point, the candidate's **original quote and recording time**, so a wrong translation can be caught

Flow: HR reviews, then sends; the manager sees it under "My interviews".

This is useful only where a Korean manager interviews. The claim that managers struggle with Vietnamese CVs is a hypothesis for HR interviews to confirm.

## 5. Scorecard

After the interview, the manager scores each requirement and gives a hire or no-hire recommendation with notes. HR records `applications.final_outcome`: `hired`, `not_hired` or `offer_declined`. Block 5's Reality Check uses this data. Scheduling stays manual.

## 6. API

```
POST /api/companies/{id}/hiring-requests
POST /api/companies/{id}/hiring-requests/{req_id}/intake/start
POST /api/companies/{id}/hiring-requests/{req_id}/drafts
GET  /api/companies/{id}/job-drafts/{draft_id}
POST /api/companies/{id}/job-drafts/{draft_id}/assistant
POST /api/companies/{id}/job-drafts/{draft_id}/submit
POST /api/companies/{id}/job-drafts/{draft_id}/approve    manager
POST /api/companies/{id}/job-drafts/{draft_id}/publish    hr
GET  /api/companies/{id}/job-drafts/{draft_id}/channels
POST /api/companies/{id}/applications/{app_id}/brief
POST /api/companies/{id}/applications/{app_id}/brief/send
GET  /api/companies/{id}/my-interviews                    manager
POST /api/companies/{id}/applications/{app_id}/scorecard  manager
POST /api/companies/{id}/applications/{app_id}/outcome    hr
```

Voice turns reuse the Block 3 turn endpoints, checking session ownership.

## 7. Error handling

- Intake disconnect resumes as in Block 3.
- AI failure in JD Studio leaves the last saved draft intact and shows an error.
- A brief cannot be sent until reviewed.
- A failed translation of one language blocks approval for that draft and shows which language failed.

## 8. Testing

`fake` provider tests: source-line validation, salary without source being rejected, HR confirmation path, lint blocking publish, discrimination guard blocking requirement creation, confidential nodes absent from JD context, `job.version` increment, manager department scoping, enumeration test.

Evaluation: `eval/discrimination/` holds labelled statements in Vietnamese, English and Korean; report precision and recall. Target recall ≥ 90%, since misses are the costly error. Real AI is required, so it runs by command.

Playwright: request, intake with fake STT, draft, assistant edit, approve, publish, brief, scorecard.

## 9. Acceptance criteria

1. A manager completes an intake in Korean and HR sees proposed nodes with verified quotes in the review queue.
2. A discriminatory statement is flagged and cannot become a requirement.
3. JD Studio produces a three-language JD where every line traces to a source or an HR confirmation.
4. Channel content exists for all four channel groups, each with a tracked link.
5. The assistant can restyle content without changing facts, and refuses unsourced salary or benefits until HR confirms.
6. Lint blocks publishing on discrimination or unresolved conflict.
7. The manager approves the Korean version, and publishing updates the job.
8. A manager receives a Korean brief with original quotes, and submits a scorecard.

## 10. Out of scope

Posting to job boards, calendar integration, video.
