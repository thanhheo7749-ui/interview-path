# SpeakCV Profile Master CV Design

## 1. Goal
SpeakCV should add a **Master CV** section to the existing profile page so each user can store one primary CV and let the interview flow use it as default context.

The point is not to build a full CV management system. The point is to create one clear source of truth for interview preparation:
- the user uploads or pastes one CV in profile
- that CV is stored as `master_cv_text`
- interview setup can use it automatically when the user provides a JD

This keeps the flow simple and removes the need to ask users to re-enter their CV every time they start an interview.

---

## 2. Product positioning
This feature should be presented as:

> A persistent Master CV in the profile that powers smarter interview context automatically.

This is stronger than:
- asking the user to paste CV text again and again
- putting CV upload only inside the interview screen
- trying to support multiple CV versions before the basic source-of-truth flow exists

The user mental model should be simple:
- profile stores my main CV
- interview uses that CV by default

---

## 3. What this feature is and is not
### This feature is
- one persistent Master CV per user
- stored as raw text after upload or paste
- editable from the profile page
- usable by interview setup to generate `interview_context`

### This feature is not
- a CV library
- multi-version CV management
- a full CV editor
- automatic rewrite of all profile fields from uploaded CV

That scope boundary is important because the codebase already has CV generation, CV review, and CV makeover flows. This feature should stay focused on interview context.

---

## 4. Current-code alignment
The design should reuse the code that already exists.

## 4.1 Existing backend pieces to reuse
- [cv.py](../src/backend/app/routers/cv.py) already has:
  - `extract_text_from_cv()` for PDF/DOCX parsing
  - `/api/cv/interview-context` for turning CV text + JD into `interview_context`
- [profile.py](../src/backend/app/routers/profile.py) already owns profile get/update behavior
- [sql_models.py](../src/backend/app/database/sql_models.py) already stores profile-level fields in `UserProfile`

## 4.2 Existing frontend pieces to reuse
- [profile/page.tsx](../src/frontend/app/profile/page.tsx) already manages profile data editing
- [api.ts](../src/frontend/services/api.ts) already contains profile and CV API helpers
- [SetupForm.tsx](../src/frontend/components/Interview/SetupForm.tsx) already collects JD and interview setup inputs
- [useChat.ts](../src/frontend/hooks/useChat.ts) already uses session storage for `interview_context`

This means the feature should be built as an extension of existing profile and CV flows, not as a new subsystem.

---

## 5. Core architecture
The feature should be implemented as four connected pieces.

## 5.1 Profile storage layer
Add one new persistent field to the profile model:
- `master_cv_text`

This field lives with other profile information and is returned by the existing profile APIs.

### Why this is the right storage shape
- the interview context route already accepts plain CV text
- storing raw text is simpler than storing uploaded files
- storing raw text avoids adding file hosting/storage concerns right now

---

## 5.2 Profile Master CV UI
Add a **Master CV** section to the existing profile page.

The section should allow two ways to set the same field:
1. **Upload PDF/DOCX**
2. **Paste CV text**

Both paths end in the same result:
- the user sees editable text
- the app saves that text as `master_cv_text`

### UI requirements
The section should show:
- section title: `Master CV`
- a short explanation that this CV will be used for interview context
- upload control for PDF/DOCX
- textarea for pasted or extracted CV text
- save button
- status message when a CV already exists

### Why both input modes are worth it
- upload is convenient for most users
- paste text is fast for copy/paste workflows and debugging
- both modes reuse one stored shape, so they do not create architectural complexity

---

## 5.3 CV text extraction endpoint for profile use
Add a small profile-adjacent upload flow that reuses existing CV extraction logic.

### Behavior
- frontend uploads a CV file
- backend extracts plain text using the existing parser
- backend returns the extracted text only
- frontend places that text into the profile Master CV textarea
- user explicitly saves profile after reviewing it

### Why explicit save matters
The system should not auto-save extracted text immediately after upload. Letting the user review and then save is safer and easier to understand.

---

## 5.4 Interview setup bootstrap
The interview setup should use the saved Master CV as default context source.

### Behavior
When the user is in interview setup:
- if `master_cv_text` exists
- and the user has entered a JD
- frontend can call `/api/cv/interview-context`
- the returned `interview_context` becomes the default session context

### UI behavior in setup
Show one lightweight status line:
- if CV exists: `Using your saved Master CV`
- if no CV exists: `No saved CV yet — interview will use JD only`

### Important boundary
Interview setup should **use** the Master CV, not **manage** it. Profile remains the place to create or update the Master CV.

---

## 6. Data flow
The intended flow should be:

## 6.1 Save path
1. user opens profile page
2. user uploads CV file or pastes CV text
3. if upload: backend extracts plain text
4. frontend fills the Master CV textarea
5. user saves profile
6. backend stores `master_cv_text`

## 6.2 Interview bootstrap path
1. user opens interview setup
2. frontend loads user profile
3. if `master_cv_text` exists and JD is present, frontend calls `/api/cv/interview-context`
4. backend returns structured interview context
5. frontend stores it in the existing `interview_context` session flow
6. interview chat uses that context automatically

---

## 7. API and model changes
### Backend model change
`UserProfile` should gain:
- `master_cv_text: Text | nullable`

### Profile update schema
`ProfileUpdate` should gain:
- `master_cv_text?: string`

### Profile API behavior
`GET /api/my-profile`
- returns `master_cv_text` inside `info`

`PUT /api/my-profile`
- accepts and saves `master_cv_text`

### New or reused CV upload route
There should be a route that returns extracted CV text for profile usage.

Preferred direction:
- add a small dedicated route using existing `extract_text_from_cv()`
- do not overload review/makeover endpoints for this

---

## 8. UX requirements
### Profile page
The Master CV section should:
- sit naturally near the rest of profile information
- feel like part of the profile, not a detached wizard
- clearly explain that it powers interview context
- support replacing the CV later

### Interview setup
The setup form should:
- avoid new upload complexity
- only surface whether a Master CV will be used
- stay lightweight and fast

### Error handling direction
Errors should stay simple and user-facing:
- unsupported file type
- failed text extraction
- empty CV text
- JD missing when trying to build context

No extra fallback architecture is needed beyond that.

---

## 9. Testing strategy
### Backend tests
Add tests for:
- profile get returns `master_cv_text`
- profile update stores `master_cv_text`
- CV text extraction route returns extracted text from supported files
- interview context route still works with stored Master CV text passed in

### Frontend verification
Verify:
- profile page renders Master CV section
- upload path fills textarea with extracted text
- paste text path saves correctly
- interview setup shows saved-CV status
- saved Master CV can be used to build `interview_context`

### Manual golden path
1. log in
2. open profile
3. upload or paste CV
4. save profile
5. open interview setup
6. enter JD
7. confirm setup uses saved Master CV context
8. start interview

---

## 10. Scope boundaries
### In scope
- one `master_cv_text` field in profile
- upload PDF/DOCX to extract CV text
- paste CV text directly
- save Master CV in profile
- interview setup uses saved Master CV by default

### Out of scope
- multiple saved CVs
- CV version switching
- CV file storage as a permanent artifact
- auto-populating full profile fields from uploaded CV
- full CV management dashboard

Keeping this scope tight is what makes the feature fit naturally into the current product.

---

## 11. Final recommendation
The best design is:
1. add one `Master CV` section to profile
2. store one `master_cv_text` field as the single source of truth
3. reuse existing CV extraction and interview-context routes
4. let interview setup consume that saved CV automatically

This gives SpeakCV a cleaner interview experience without creating a second profile-like system inside the interview flow.

In short:
- **profile owns the Master CV**
- **interview consumes the Master CV**
- **the user only has to provide it once**
