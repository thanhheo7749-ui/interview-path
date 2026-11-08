# Phase 04 — Prefill from the candidate's application + fit-page link

## Context Links
- Overview: [plan.md](plan.md). Open Questions 3, 7, 8, 9 and 10 shape this phase. The steps assume the recommended answers.
- Link today: `SpeakCV/src/frontend/app/applications/[id]/fit/page.tsx:154-159`. It is `LEGACY_B2C`-gated and lives in **SpeakCV**, not interviewpath-demo.
- Page gate: `app/interview/layout.tsx:3-6` (`notFound()` unless `NEXT_PUBLIC_LEGACY_B2C_ENABLED=true`, default false)
- Client: `services/hiring.ts:156` (`getApplication(id)`, auth), `:140-141` (`getPublicJob(slug, src?)`, no auth), `:24-36` and `:41-66` (types)
- Backend: `routers/applications.py:233-235` (owner-only via `_owned`), `routers/public_jobs.py:16-39` (published/closed jobs; counts clicks only when `src` is given)
- URL-param precedent: `app/interview/page.tsx:86` (`next`)
- Existing CV-title fill: `app/interview/page.tsx:134-143`

## Overview
- Priority: P2. Status: pending. Blocked by: phases 1 and 3.
- `fit` link adds `&applicationId={id}`. `/interview` loads title, company and JD from the candidate's own application and prefills Setup.

## Key Insights
- Same backend and same `users` table. The candidate is already logged in on the SpeakCV origin. **No new token is needed.** Do NOT reuse `JobChannelLink` / `?src=` (`hiring/jobs.py:206`, `bridges/channels.py:75-76`). That token is channel attribution on a public job link. It does not prove who the candidate is, and passing it here would inflate click counts.
- `getPublicJob(slug)` is called **without** `src`, so analytics stay unchanged.
- The ownership check lives in the backend (`_owned`). The frontend must still treat any failure as "no prefill" and show no partial data.
- With `applicationId`, the CV-title effect (`page.tsx:134-143`) must skip. Otherwise it fills Position before the job title arrives, and the "only if empty" rule then blocks the job title.

## Requirements
Functional:
- Fit link: `/interview?next=${enc(screening)}&applicationId=${applicationId}`.
- `/interview` reads `applicationId`. It accepts it only if it matches `^[1-9]\d{0,9}$`, the user is logged in (OQ 10a), and `PRACTICE_STEP_FLOW` is on (OQ 2a).
- Flow: `getApplication(id)` returns `{job_title, company_name, job_slug}`. If `job_slug` is set, call `getPublicJob(job_slug)` to get `{description, requirements}`.
- JD = description, plus "\n\nRequirements:\n- ..." built from the public requirements (OQ 8a).
- Prefill position/company/JD through `resolvePrefill`, with the app source at top priority. The never-overwrite-user-input rule still applies. When an applicationId is present, history and the CV title do not fill those 3 fields.
- Any error is silent: a console warning, and the form stays as it is (OQ 9a).
- Notice line: "Filled from your application: {job_title} at {company_name}". This reuses the phase 3 notice component.
Non-functional: one request at a time, aborted on unmount (`AbortController`, or an `ignore` flag in the effect).

## Architecture / Data flow
```
fit page --(link ?next=..&applicationId=N)--> /interview
 usePracticePrefill: validate N -> getApplication(N) [Bearer, owner-only, 404 otherwise]
   -> job_slug? getPublicJob(slug) [public, no src]
   -> resolvePrefill({app:{position,company,jd}, ...}) -> setConfig
 Start -> normal flow; end-interview stores company/JD (phase 1) -> next visit prefills from history
```

## Related Code Files
Modify:
- `app/applications/[id]/fit/page.tsx`: 1-line href change. This is its own small step, and it touches only this file.
- `services/hiring.ts`: add `job_slug?: string | null` to the `Application` type
- `hooks/usePracticePrefill.ts`: add the app source (if the file passes about 150 lines, split it into `hooks/useApplicationPracticeContext.ts`)
- `lib/practicePrefill.ts`: app source has top priority; skip the history and CV sources for position/company/JD when an app source is present
- `app/interview/page.tsx`: read `applicationId`; add the skip guard to the CV-title effect (`if (applicationId) return;`)
Create: maybe `hooks/useApplicationPracticeContext.ts` (fetch + compose JD, under 80 lines)
Delete: none

## Implementation Steps
1. Add the `job_slug` type field.
2. Write the fetch helper: validate the id, call `getApplication`, then call `getPublicJob` if there is a slug. Return `{position, company, jd}` or `null`.
3. Add it as the app source in `resolvePrefill`, and wire it into the hook.
4. Add the CV-title skip guard in `page.tsx`.
5. Change the fit-page link.
6. Build and lint.

## Todo List
- [ ] Application type job_slug
- [ ] fetch + compose helper
- [ ] app source in resolvePrefill/hook
- [ ] CV-title guard
- [ ] fit link `&applicationId=`
- [ ] build + lint

## Success Criteria
(Run with `NEXT_PUBLIC_LEGACY_B2C_ENABLED=true`.)
- An invited candidate clicks "Practice first". Setup shows job title, company and JD (description + requirements), and the `?next=` banner still links to screening.
- Change the URL to another user's application id: nothing is prefilled, there is no error UI, and the network shows a 404.
- `applicationId=abc`, `0`, or `-1`: no request is made.
- Logged out: no request is made.
- Default flags (`LEGACY_B2C` false): the fit page shows no link and `/interview` returns 404. This is unchanged, and expected.

## Risk Assessment
| Risk | L x I | Mitigation |
|---|---|---|
| IDOR (reading someone else's application) | L x H | Backend `_owned` + phase 1 cross-user test |
| CV-title fills Position first | H x M | Skip guard when an applicationId is present |
| Job unpublished/draft: public endpoint 404 | M x L | Title/company still fill; JD stays empty |
| Job description language differs from the practice voice | M x L | Accepted; note only |
| Feature "does nothing" in default deploy | H x L | Called out in plan.md; flag default unchanged by design |

## Rollback
Revert the fit-page href, then the hook source. The backend `job_slug` field is harmless if left in place.

## Security Considerations
- No identity or job data is in the URL, only an integer id. The server decides what the caller may see.
- Validate the id before any fetch. Never put the URL value into the DOM.
- The public endpoint is called without `src`, so it cannot be used to inflate channel clicks.

## Next Steps
Phase 5 verification.
