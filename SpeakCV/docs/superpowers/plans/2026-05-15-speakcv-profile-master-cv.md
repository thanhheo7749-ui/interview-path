# SpeakCV Profile Master CV Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a single persistent Master CV to the profile page so users can upload or paste one CV, save it as `master_cv_text`, and let interview setup use it as the default context source when a JD is present.

**Architecture:** Extend the existing `UserProfile` storage model and `GET/PUT /api/my-profile` endpoints with one new `master_cv_text` field. Reuse the existing CV text extraction helper in `cv.py` through a small dedicated extraction route, then reuse the existing `/api/cv/interview-context` endpoint plus the current `sessionStorage`-based interview context flow so the interview screen consumes the saved Master CV without adding a second CV-management system.

**Tech Stack:** FastAPI, SQLAlchemy models, Pydantic models, pytest, Next.js App Router, React state/hooks, existing fetch-based API helpers, existing profile page and interview setup form.

---

## File structure

### Backend files to modify
- `src/backend/app/database/sql_models.py`
  - Add `master_cv_text` to `UserProfile`.
- `src/backend/app/models.py`
  - Extend `ProfileUpdate` with `master_cv_text` and add a request model for CV text extraction if needed.
- `src/backend/app/routers/profile.py`
  - Return and save `master_cv_text` through existing profile APIs.
- `src/backend/app/routers/cv.py`
  - Add a small extraction-only route for profile CV uploads, reusing `extract_text_from_cv()`.

### Backend files to create
- `src/backend/tests/test_profile_master_cv.py`
  - Cover storing and retrieving `master_cv_text`.
- `src/backend/tests/test_cv_extract_text_route.py`
  - Cover extracting raw CV text from uploaded PDF/DOCX for profile usage.

### Frontend files to modify
- `src/frontend/services/api.ts`
  - Add API helpers for Master CV text extraction and saving `master_cv_text` in profile.
- `src/frontend/app/profile/page.tsx`
  - Add the Master CV section with upload + paste + save behavior.
- `src/frontend/components/Interview/SetupForm.tsx`
  - Show whether a saved Master CV is available for interview context.
- `src/frontend/app/interview/page.tsx`
  - Load profile CV context availability and bootstrap `interview_context` when JD is present.
- `src/frontend/hooks/useChat.ts`
  - Keep reusing the existing `sessionStorage`-based `interview_context` flow; no new storage system.

### Frontend files to create
- None required if the Master CV UI can fit cleanly into the existing profile page. Keep scope small.

---

### Task 1: Add backend contract tests for Master CV profile storage

**Files:**
- Create: `src/backend/tests/test_profile_master_cv.py`
- Modify: `src/backend/app/database/sql_models.py:23-36`
- Modify: `src/backend/app/models.py:11-20`
- Modify: `src/backend/app/routers/profile.py:27-71`

- [ ] **Step 1: Write the failing profile retrieval test**

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import profile


def test_get_my_profile_returns_master_cv_text(monkeypatch):
    app = FastAPI()
    app.include_router(profile.router)
    client = TestClient(app)

    class FakeUser:
        id = 1
        full_name = "Admin"
        email = "admin@gmail.com"
        role = "admin"
        credits = 100
        plan = "pro"

    class FakeProfile:
        user_id = 1
        phone = None
        address = None
        website = None
        github = None
        linkedin = None
        summary = None
        skills = None
        avatar = None
        master_cv_text = "Python, FastAPI, Redis"

    class FakeQuery:
        def __init__(self, result):
            self.result = result

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return self.result

        def all(self):
            return []

    class FakeDB:
        def query(self, model):
            if model.__name__ == "UserProfile":
                return FakeQuery(FakeProfile())
            return FakeQuery([])

        def add(self, value):
            pass

        def commit(self):
            pass

        def refresh(self, value):
            pass

    app.dependency_overrides[profile.get_current_user] = lambda: FakeUser()
    app.dependency_overrides[profile.database.get_db] = lambda: FakeDB()

    response = client.get("/api/my-profile")

    assert response.status_code == 200
    assert response.json()["info"]["master_cv_text"] == "Python, FastAPI, Redis"
```

- [ ] **Step 2: Run the retrieval test to verify it fails**

Run:
```bash
pytest src/backend/tests/test_profile_master_cv.py::test_get_my_profile_returns_master_cv_text -v
```

Expected: FAIL because `master_cv_text` is not part of `UserProfile` yet.

- [ ] **Step 3: Write the failing profile update test**

```python
def test_update_profile_saves_master_cv_text(monkeypatch):
    app = FastAPI()
    app.include_router(profile.router)
    client = TestClient(app)

    class FakeUser:
        id = 1
        full_name = "Admin"
        email = "admin@gmail.com"

    class FakeProfile:
        user_id = 1
        phone = None
        address = None
        website = None
        github = None
        linkedin = None
        summary = None
        skills = None
        avatar = None
        master_cv_text = None

    stored = FakeProfile()

    class FakeQuery:
        def __init__(self, result):
            self.result = result

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return self.result

    class FakeDB:
        def query(self, model):
            return FakeQuery(stored)

        def add(self, value):
            pass

        def commit(self):
            pass

    app.dependency_overrides[profile.get_current_user] = lambda: FakeUser()
    app.dependency_overrides[profile.database.get_db] = lambda: FakeDB()

    response = client.put(
        "/api/my-profile",
        json={"master_cv_text": "Built APIs with FastAPI and PostgreSQL."},
    )

    assert response.status_code == 200
    assert stored.master_cv_text == "Built APIs with FastAPI and PostgreSQL."
```

- [ ] **Step 4: Run the update test to verify it fails**

Run:
```bash
pytest src/backend/tests/test_profile_master_cv.py::test_update_profile_saves_master_cv_text -v
```

Expected: FAIL because `ProfileUpdate` and `update_profile()` do not support `master_cv_text` yet.

- [ ] **Step 5: Implement the minimal backend model/storage change**

In `src/backend/app/database/sql_models.py`, extend `UserProfile`:

```python
class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    phone = Column(String(20), nullable=True)
    address = Column(String(255), nullable=True)
    website = Column(String(255), nullable=True)
    github = Column(String(255), nullable=True)
    linkedin = Column(String(255), nullable=True)
    summary = Column(Text, nullable=True)
    skills = Column(Text, nullable=True)
    avatar = Column(Text, nullable=True)
    master_cv_text = Column(Text, nullable=True)
```

In `src/backend/app/models.py`, extend `ProfileUpdate`:

```python
class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    github: Optional[str] = None
    linkedin: Optional[str] = None
    summary: Optional[str] = None
    skills: Optional[str] = None
    avatar: Optional[str] = None
    master_cv_text: Optional[str] = None
```

In `src/backend/app/routers/profile.py`, save the new field:

```python
if data.master_cv_text is not None:
    profile.master_cv_text = data.master_cv_text
```

- [ ] **Step 6: Run the profile Master CV tests to verify they pass**

Run:
```bash
pytest src/backend/tests/test_profile_master_cv.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/backend/app/database/sql_models.py src/backend/app/models.py src/backend/app/routers/profile.py src/backend/tests/test_profile_master_cv.py
git commit -m "feat: add master cv storage to user profile"
```

---

### Task 2: Add a dedicated CV text extraction route for profile uploads

**Files:**
- Create: `src/backend/tests/test_cv_extract_text_route.py`
- Modify: `src/backend/app/models.py:80-90`
- Modify: `src/backend/app/routers/cv.py:24-82`

- [ ] **Step 1: Write the failing extraction-route test**

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.cv import router


app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_extract_master_cv_text_returns_plain_text(monkeypatch):
    async def fake_extract(file):
        return "Python\nFastAPI\nRedis"

    monkeypatch.setattr("app.routers.cv.extract_text_from_cv", fake_extract)

    response = client.post(
        "/api/cv/extract-text",
        files={"file": ("resume.pdf", b"fake-pdf-content", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json() == {"extracted_text": "Python\nFastAPI\nRedis"}
```

- [ ] **Step 2: Run the extraction-route test to verify it fails**

Run:
```bash
pytest src/backend/tests/test_cv_extract_text_route.py::test_extract_master_cv_text_returns_plain_text -v
```

Expected: FAIL because `/api/cv/extract-text` does not exist yet.

- [ ] **Step 3: Add the smallest request/response support needed**

If a request model is unnecessary, do not add one. The route can stay file-based only.

In `src/backend/app/routers/cv.py`, add:

```python
@router.post("/api/cv/extract-text")
async def extract_cv_text_route(file: UploadFile = File(...)):
    extracted_text = await extract_text_from_cv(file)
    return {"extracted_text": extracted_text}
```

- [ ] **Step 4: Run the extraction-route test to verify it passes**

Run:
```bash
pytest src/backend/tests/test_cv_extract_text_route.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/backend/app/routers/cv.py src/backend/tests/test_cv_extract_text_route.py
git commit -m "feat: add cv text extraction route for profile uploads"
```

---

### Task 3: Add frontend API helpers for Master CV profile flows

**Files:**
- Modify: `src/frontend/services/api.ts:167-262`

- [ ] **Step 1: Write the failing API helper shape in code comments/tests-by-usage**

Add the target helper signatures near the profile APIs:

```ts
export const extractCVText = async (file: File) => {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_URL}/cv/extract-text`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) throw new Error("Failed to extract CV text");
  return res.json();
};
```

And rely on the build to fail once the profile page tries to use it before it exists.

- [ ] **Step 2: Run the frontend build after wiring call sites to verify it fails**

Run:
```bash
npm --prefix src/frontend run build
```

Expected: FAIL if the profile page references `extractCVText` before it exists.

- [ ] **Step 3: Implement the helper minimally**

Add to `src/frontend/services/api.ts`:

```ts
export const extractCVText = async (file: File) => {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_URL}/cv/extract-text`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) throw new Error("Failed to extract CV text");
  return res.json();
};
```

- [ ] **Step 4: Re-run the frontend build after later call-site wiring**

Run:
```bash
npm --prefix src/frontend run build
```

Expected: PASS once Task 4 is complete.

- [ ] **Step 5: Commit**

```bash
git add src/frontend/services/api.ts
git commit -m "feat: add master cv profile api helpers"
```

---

### Task 4: Add the Master CV section to the profile page

**Files:**
- Modify: `src/frontend/app/profile/page.tsx:31-420`
- Modify: `src/frontend/services/api.ts`

- [ ] **Step 1: Write the failing UI behavior by consuming the new profile field**

Extend the profile state expectations in `page.tsx` by reading and editing `info.master_cv_text`, and use the new `extractCVText()` helper. This should fail the build until the code is wired correctly.

Target local state additions:

```ts
const [cvInputMode, setCvInputMode] = useState<"upload" | "paste">("upload");
const [extractingCv, setExtractingCv] = useState(false);
```

Target profile behavior:

```ts
const handleMasterCvUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
  const file = e.target.files?.[0];
  if (!file) return;
  setExtractingCv(true);
  try {
    const data = await extractCVText(file);
    setInfo((prev: any) => ({ ...prev, master_cv_text: data.extracted_text || "" }));
  } finally {
    setExtractingCv(false);
  }
};
```

- [ ] **Step 2: Run the frontend build to verify it fails for missing or mismatched wiring**

Run:
```bash
npm --prefix src/frontend run build
```

Expected: FAIL before all imports/state/UI are wired correctly.

- [ ] **Step 3: Implement the Master CV section minimally**

Add a new section after personal info and before work experience:

```tsx
<div className="bg-theme-primary p-6 md:p-8 rounded-3xl border border-theme-border shadow-xl">
  <div className="flex items-center justify-between gap-4 mb-6">
    <div>
      <h2 className="text-xl font-bold text-white">Master CV</h2>
      <p className="text-theme-text-secondary text-sm mt-2">
        CV này sẽ được dùng làm nguồn context mặc định cho interview.
      </p>
    </div>
  </div>

  <div className="flex gap-3 mb-4">
    <button
      onClick={() => setCvInputMode("upload")}
      className={`px-4 py-2 rounded-xl font-bold ${cvInputMode === "upload" ? "bg-blue-600 text-white" : "bg-theme-secondary text-theme-text-secondary"}`}
    >
      Upload file
    </button>
    <button
      onClick={() => setCvInputMode("paste")}
      className={`px-4 py-2 rounded-xl font-bold ${cvInputMode === "paste" ? "bg-blue-600 text-white" : "bg-theme-secondary text-theme-text-secondary"}`}
    >
      Paste text
    </button>
  </div>

  {cvInputMode === "upload" && (
    <div className="mb-4">
      <input type="file" accept=".pdf,.doc,.docx" onChange={handleMasterCvUpload} />
      <p className="text-xs text-theme-text-secondary mt-2">PDF hoặc DOCX. Nội dung sẽ được trích xuất thành text trước khi lưu.</p>
    </div>
  )}

  <textarea
    className="w-full bg-theme-secondary border border-theme-border focus:border-blue-600 outline-none p-3 rounded-xl mt-2 h-48 custom-scrollbar"
    value={info.master_cv_text || ""}
    onChange={(e) => setInfo({ ...info, master_cv_text: e.target.value })}
    placeholder="Dán CV text vào đây hoặc upload file để tự động trích xuất..."
  />

  <div className="mt-3 text-sm text-theme-text-secondary">
    {extractingCv ? "Đang trích xuất nội dung CV..." : info.master_cv_text ? "Master CV đã sẵn sàng để dùng cho interview." : "Chưa có Master CV nào được lưu."}
  </div>
</div>
```

Do not add a second save button. Reuse the existing profile save button so the mental model stays simple.

- [ ] **Step 4: Run the frontend build to verify it passes**

Run:
```bash
npm --prefix src/frontend run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/frontend/app/profile/page.tsx src/frontend/services/api.ts
git commit -m "feat: add master cv section to profile"
```

---

### Task 5: Use saved Master CV in interview setup bootstrap

**Files:**
- Modify: `src/frontend/components/Interview/SetupForm.tsx:11-80`
- Modify: `src/frontend/app/interview/page.tsx:35-324`
- Modify: `src/frontend/services/api.ts`

- [ ] **Step 1: Write the failing bootstrap behavior by referencing Master CV state in interview setup**

Target helper in `api.ts`:

```ts
export const buildInterviewContext = async (cvText: string, jdText: string) => {
  const res = await apiRequest(`${API_URL}/cv/interview-context`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cv_text: cvText, jd_text: jdText }),
  });
  return res.json();
};
```

Target prop additions for `SetupForm`:

```ts
masterCvAvailable?: boolean;
masterCvStatus?: string;
```

- [ ] **Step 2: Run the frontend build to verify wiring gaps fail first**

Run:
```bash
npm --prefix src/frontend run build
```

Expected: FAIL until the page and setup form are fully wired.

- [ ] **Step 3: Implement the smallest context bootstrap path**

In `page.tsx`, after loading profile data, keep `master_cv_text` in state through `config` or a small local variable. When JD changes or when starting interview, call `buildInterviewContext()` if both values exist.

Use the existing session storage key used by `useChat.ts`:

```ts
const persistInterviewContext = (context: Record<string, unknown> | null) => {
  if (!context) {
    sessionStorage.removeItem("interview_context");
    return;
  }
  sessionStorage.setItem("interview_context", JSON.stringify(context));
};
```

Before starting the interview:

```ts
if (masterCvText?.trim() && config.jd.trim()) {
  const result = await buildInterviewContext(masterCvText, config.jd);
  persistInterviewContext(result.interview_context || null);
} else if (!masterCvText?.trim()) {
  persistInterviewContext(null);
}
```

In `SetupForm.tsx`, add a small status block below JD:

```tsx
<div className="text-sm text-theme-text-secondary rounded-xl bg-theme-secondary/60 border border-theme-border px-4 py-3">
  {masterCvAvailable
    ? "Using your saved Master CV as the default interview context source."
    : "No saved Master CV yet — interview will use JD only."}
</div>
```

- [ ] **Step 4: Run the frontend build to verify it passes**

Run:
```bash
npm --prefix src/frontend run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/frontend/components/Interview/SetupForm.tsx src/frontend/app/interview/page.tsx src/frontend/services/api.ts
git commit -m "feat: bootstrap interview context from master cv"
```

---

### Task 6: Final verification for Master CV flow

**Files:**
- Verify only

- [ ] **Step 1: Run backend tests for the Master CV feature**

Run:
```bash
pytest src/backend/tests/test_profile_master_cv.py src/backend/tests/test_cv_extract_text_route.py src/backend/tests/test_interview_context.py -v
```

Expected: PASS.

- [ ] **Step 2: Run the frontend production build**

Run:
```bash
npm --prefix src/frontend run build
```

Expected: PASS.

- [ ] **Step 3: Verify the manual golden path**

Verify manually:
1. Log in
2. Open `/profile`
3. Paste CV text and save
4. Refresh profile and confirm text persists
5. Upload a PDF/DOCX and confirm textarea fills with extracted text
6. Save again
7. Open `/interview`
8. Enter a JD
9. Confirm setup shows saved-CV status
10. Start interview and confirm the session has `interview_context`

Expected:
- saved Master CV persists
- upload extraction works
- interview uses saved CV as default context source

- [ ] **Step 4: Commit**

```bash
git add src/backend/app/database/sql_models.py src/backend/app/models.py src/backend/app/routers/profile.py src/backend/app/routers/cv.py src/backend/tests/test_profile_master_cv.py src/backend/tests/test_cv_extract_text_route.py src/frontend/services/api.ts src/frontend/app/profile/page.tsx src/frontend/components/Interview/SetupForm.tsx src/frontend/app/interview/page.tsx
git commit -m "feat: add master cv profile flow"
```

---

## Self-review against spec

### Spec coverage
- Master CV stored once in profile: covered by Task 1.
- Upload PDF/DOCX and paste text: covered by Tasks 2 and 4.
- Reuse existing CV extraction helper: covered by Task 2.
- Interview setup uses saved Master CV by default: covered by Task 5.
- Reuse `sessionStorage` interview context flow: covered by Task 5.
- Keep scope to one Master CV, not a CV library: preserved across all tasks.

### Placeholder scan
- No TBD/TODO placeholders remain.
- Each code step includes concrete code.
- Each verification step includes exact commands.

### Type consistency
- `master_cv_text` is used consistently across backend model, profile API, profile page, and interview bootstrap.
- `interview_context` remains the existing session-storage key and API payload concept.

---

Plan complete and saved to `docs/superpowers/plans/2026-05-15-speakcv-profile-master-cv.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**