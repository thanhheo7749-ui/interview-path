# SpeakCV Profile Master CV Raw+Structured Design

## 1. Goal
SpeakCV should evolve the Master CV feature from a raw-text-only profile field into a **raw input + structured CV model** flow.

The user should still be able to:
- upload a PDF/DOCX CV
- or paste CV text directly

But the system should no longer rely on raw pasted text as the main source for interview context. Instead, it should:
1. keep the raw CV text as source input,
2. parse it immediately into a structured CV model,
3. validate that model,
4. store both raw and structured forms,
5. use the structured form as the main source for interview context.

This makes the feature much more stable when users paste messy text copied from PDF or Word files.

---

## 2. Product positioning
This feature should be presented as:

> A persistent Master CV pipeline that stores both the original CV input and a normalized structured CV representation for smarter interview preparation.

This is stronger than:
- saving only pasted text and hoping the interview flow can interpret it later
- reparsing raw CV text every time the user starts an interview
- mixing CV parsing, CV editing, and interview bootstrapping into one ambiguous step

The user mental model should stay simple:
- I upload or paste my CV once
- SpeakCV structures it for me
- interviews use that structured CV automatically

---

## 3. What this feature is and is not
### This feature is
- one Master CV per user
- saved in both raw and structured form
- parsed immediately after upload or paste
- validated before being used in interview setup
- reusable later by other CV-related flows

### This feature is not
- a multi-CV library
- a full structured CV editor
- automatic overwrite of all profile fields from the CV
- a version-history system for CVs

That boundary is important because the current codebase already has separate CV generation, makeover, review, and tailor flows.

---

## 4. Current-code alignment
The codebase already contains most of the pieces needed for this design.

## 4.1 Existing backend pieces to reuse
- [cv.py](../src/backend/app/routers/cv.py) already has:
  - `extract_text_from_cv()` for PDF/DOCX parsing
  - `parse_and_validate_cv()` for JSON parsing + validation
  - `upload_makeover_cv()` which already demonstrates text -> LLM -> JSON -> validated CV flow
- [models.py](../src/backend/app/models.py) already defines [CVMakeoverData](../src/backend/app/models.py#L213-L219) as a structured CV schema
- [profile.py](../src/backend/app/routers/profile.py) already owns profile storage and retrieval
- [cv.py](../src/backend/app/routers/cv.py#L78-L82) already exposes `/api/cv/interview-context`

## 4.2 Existing frontend pieces to reuse
- [profile/page.tsx](../src/frontend/app/profile/page.tsx) already manages profile editing
- [api.ts](../src/frontend/services/api.ts) already owns profile/CV API helpers
- [SetupForm.tsx](../src/frontend/components/Interview/SetupForm.tsx) already surfaces interview setup context
- [useChat.ts](../src/frontend/hooks/useChat.ts) already persists `interview_context` in session storage
- [CVMakeover.tsx](../src/frontend/components/Modals/CV/CVMakeover.tsx) already demonstrates frontend handling of extracted CV text and structured CV data

This means the right approach is to extract a **parse-only Master CV pipeline** from existing patterns, not invent a new CV parser architecture.

---

## 5. Core architecture
The Master CV feature should be broken into four clear units.

## 5.1 Raw input layer
### Input sources
- uploaded PDF/DOCX file
- pasted CV text

### Stored field
- `master_cv_text`

### Role
Preserve the original CV input so the system has a canonical raw source for debugging, reparsing, and future workflows.

### Why it matters
Raw input is still useful because:
- file extraction can be imperfect
- pasted text can be messy
- structured parsing may need to be rerun later

---

## 5.2 Structured normalization layer
### Stored field
- `master_cv_structured`

### Expected type
A validated object shaped like `CVMakeoverData`.

### Role
Convert raw CV text into normalized structured data immediately after upload or paste.

### Why it matters
Interview context and downstream reuse should depend on structured CV data, not directly on raw pasted text.

---

## 5.3 Parse execution layer
### Behavior
After the user uploads a file or pastes text:
1. obtain raw text,
2. send raw text into a parse-only CV normalization route,
3. validate result using `CVMakeoverData`,
4. store both raw text and structured JSON.

### Important distinction
This layer should not be framed as `makeover` or `tailor`.
It is a **parse-and-normalize** flow.

### Why it matters
The existing `upload_makeover_cv()` route proves the architecture works, but the Master CV feature should not carry makeover semantics. It needs a narrower, more stable meaning.

---

## 5.4 Interview context layer
### Role
Use `master_cv_structured` as the preferred source when building interview context.

### Behavior
Interview setup should not depend on raw CV text directly unless there is a controlled fallback.

### Why it matters
Structured CV data is much less fragile than raw text copied from PDFs, especially for skills, experience, and summary fields.

---

## 6. Data flow
The intended flow should work like this.

## 6.1 Upload file path
1. user uploads PDF/DOCX in profile
2. backend extracts raw text via `extract_text_from_cv()`
3. backend runs parse-only structured normalization
4. backend validates output with `CVMakeoverData`
5. frontend receives:
   - extracted raw text
   - structured CV object
6. user saves profile
7. backend stores:
   - `master_cv_text`
   - `master_cv_structured`

## 6.2 Paste text path
1. user pastes CV text in profile
2. frontend sends text to parse-only normalization route
3. backend parses and validates structured CV
4. frontend receives structured CV object
5. user saves profile
6. backend stores both raw and structured forms

## 6.3 Interview bootstrap path
1. user opens interview setup
2. frontend loads profile
3. if `master_cv_structured` exists and JD is present, frontend builds interview context from the structured CV representation
4. resulting `interview_context` is stored in the existing session-storage flow
5. interview chat consumes it automatically

---

## 7. Storage model
The profile should persist at least these two new fields:
- `master_cv_text`
- `master_cv_structured`

Optional fields that may be useful later but are not required in the first implementation:
- `master_cv_parse_status`
- `master_cv_updated_at`

For the first version, only raw + structured should be mandatory.

---

## 8. API changes
### Profile API changes
`GET /api/my-profile`
- returns `master_cv_text`
- returns `master_cv_structured`

`PUT /api/my-profile`
- accepts `master_cv_text`
- accepts `master_cv_structured`

### CV API changes
The backend should expose two narrow-purpose helpers:

1. **Extract raw text from file**
- upload PDF/DOCX
- return `extracted_text`

2. **Parse raw CV text into structured CV**
- input: raw CV text
- output: validated structured CV JSON matching `CVMakeoverData`

### Why a separate parse-only route matters
It lets Master CV reuse the existing schema and validation logic without pretending the user is asking for a makeover.

---

## 9. UI behavior
## 9.1 Profile page
The Master CV section should show:
- upload option
- paste option
- raw text textarea
- parse status
- concise structured summary

### Structured summary should be lightweight
Do not show raw JSON. Show only a small digest such as:
- name / title
- top skills
- number of experience entries
- number of project entries

### State model
The UI should clearly communicate three states:
- empty
- parsing
- ready

If parsing fails, the section should show that the CV could not be normalized yet.

## 9.2 Interview setup
Interview setup should show only lightweight status such as:
- `Using your structured Master CV`
- `No saved Master CV yet — interview will use JD only`
- `Master CV exists but parsing is incomplete`

Interview setup should not become a second profile editor.

---

## 10. Error-handling direction
This feature should handle these cases clearly:
- unsupported file type
- file extraction failure
- empty pasted text
- structured parse failure
- partial structured parse with missing fields

The important behavior is:
- raw text may still exist,
- but interview setup should not treat it as fully ready structured context until normalization succeeds.

---

## 11. Testing strategy
### Backend tests
Add tests for:
- storing and retrieving `master_cv_text`
- storing and retrieving `master_cv_structured`
- extraction route returns raw text
- parse-only route returns validated structured data
- parse-only route rejects invalid structured output

### Frontend verification
Verify:
- profile page can upload file and receive extracted text
- profile page can paste text and trigger structured parse
- structured summary renders when parse succeeds
- setup form shows structured Master CV status correctly
- interview setup uses structured Master CV context when available

### Manual golden path
1. log in
2. open profile
3. upload PDF/DOCX or paste CV text
4. wait for parse
5. confirm structured summary appears
6. save profile
7. refresh profile and confirm raw + structured CV still exist
8. open interview setup
9. enter JD
10. confirm structured Master CV is used for context bootstrapping

---

## 12. Scope boundaries
### In scope
- one raw Master CV input
- one structured Master CV representation
- immediate parse after upload or paste
- validation through `CVMakeoverData`
- interview setup consuming structured CV by default

### Out of scope
- multiple CV versions
- full structured CV editing UI
- auto-syncing structured CV into all profile fields
- CV diff/history management
- complete replacement of current CV makeover/tailor flows

This keeps the design focused and buildable.

---

## 13. Final recommendation
The best direction is:
1. keep raw CV text as source input
2. immediately normalize it into structured CV data
3. validate with the existing `CVMakeoverData` schema
4. store both forms in profile
5. let interview setup consume the structured form by default

This gives SpeakCV a much stronger Master CV foundation because interview quality is no longer tied directly to messy raw pasted text.

In short:
- **raw text is the source input**
- **structured CV is the canonical working form**
- **interview should consume the structured form first**
