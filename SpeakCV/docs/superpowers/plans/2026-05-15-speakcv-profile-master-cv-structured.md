# SpeakCV Profile Master CV Raw+Structured Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade Master CV from raw-text-only storage into a raw + structured CV pipeline so the profile stores both `master_cv_text` and `master_cv_structured`, and interview setup uses the structured form as the default context source.

**Architecture:** Reuse the existing CV extraction helper, JSON validation via `CVMakeoverData`, and the current `/api/cv/interview-context` plus `sessionStorage` interview-context flow. Add a parse-only backend route that turns raw CV text into validated structured CV data, store both raw and structured forms in the profile, and update profile/interview frontend flows to depend on the structured form instead of raw pasted text.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, Next.js App Router, React hooks/state, existing fetch-based frontend API helpers, existing profile page and interview setup form.

---

## File structure

### Backend files to modify
- `src/backend/app/database/sql_models.py`
  - Extend `UserProfile` with `master_cv_structured`.
- `src/backend/app/models.py`
  - Extend `ProfileUpdate` with `master_cv_structured` and add a parse-only request model.
- `src/backend/app/routers/profile.py`
  - Return and save `master_cv_structured` along with `master_cv_text`.
- `src/backend/app/routers/cv.py`
  - Add a parse-only route that turns raw CV text into validated `CVMakeoverData`.
- `src/backend/app/main.py`
  - Ensure local schema bootstrap also adds `master_cv_structured` to existing databases if missing.

### Backend files to create
- `src/backend/tests/test_profile_master_cv_structured.py`
  - Cover storing and retrieving `master_cv_structured`.
- `src/backend/tests/test_cv_parse_master_cv_route.py`
  - Cover parse-only structured normalization route behavior.

### Frontend files to modify
- `src/frontend/services/api.ts`
  - Add helper for parse-only structured CV normalization.
- `src/frontend/app/profile/page.tsx`
  - Parse immediately after upload/paste, show structured summary, and save raw + structured together.
- `src/frontend/app/interview/page.tsx`
  - Bootstrap interview context from `master_cv_structured` instead of raw text.
- `src/frontend/components/Interview/SetupForm.tsx`
  - Show status of structured Master CV readiness.

### Frontend files to create
- None required in the first version. Keep the UI inside the existing profile page.

---

### Task 1: Add backend tests and storage for `master_cv_structured`

**Files:**
- Create: `src/backend/tests/test_profile_master_cv_structured.py`
- Modify: `src/backend/app/database/sql_models.py:23-36`
- Modify: `src/backend/app/models.py:11-20`
- Modify: `src/backend/app/routers/profile.py:27-73`
- Modify: `src/backend/app/main.py:27-70`

- [ ] **Step 1: Write the failing retrieval test for structured Master CV**

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.database import get_db
from app.database.sql_models import Base, User, UserProfile
from app.routers.profile import get_current_user, router

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

app = FastAPI()
app.include_router(router)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def override_get_current_user():
    db = TestingSessionLocal()
    try:
        return db.query(User).filter(User.email == "test@example.com").first()
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user
client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        user = User(
            email="test@example.com",
            full_name="Test User",
            hashed_password="hashed",
            role="user",
            credits=50,
            plan="free",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        profile = UserProfile(
            user_id=user.id,
            master_cv_text="Raw CV text",
            master_cv_structured={
                "personal_info": {"name": "Test User", "title": "Backend Engineer"},
                "skills": ["Python", "FastAPI"],
                "experience": [],
                "education": [],
                "projects": [],
                "analysis_feedback": {"strengths": [], "weaknesses": [], "overall_score": 0},
            },
        )
        db.add(profile)
        db.commit()
    finally:
        db.close()


def test_get_my_profile_returns_master_cv_structured_in_info():
    response = client.get("/api/my-profile")

    assert response.status_code == 200
    payload = response.json()
    assert payload["info"]["master_cv_structured"]["personal_info"]["name"] == "Test User"
    assert payload["info"]["master_cv_structured"]["skills"] == ["Python", "FastAPI"]
```

- [ ] **Step 2: Run the retrieval test to verify it fails**

Run:
```bash
pytest src/backend/tests/test_profile_master_cv_structured.py::test_get_my_profile_returns_master_cv_structured_in_info -v
```

Expected: FAIL because `master_cv_structured` is not yet part of `UserProfile`.

- [ ] **Step 3: Write the failing update test for structured Master CV**

```python
def test_update_profile_saves_master_cv_structured():
    response = client.put(
        "/api/my-profile",
        json={
            "master_cv_structured": {
                "personal_info": {"name": "Updated User", "title": "Platform Engineer"},
                "skills": ["Redis", "Docker"],
                "experience": [],
                "education": [],
                "projects": [],
                "analysis_feedback": {"strengths": [], "weaknesses": [], "overall_score": 0},
            }
        },
    )

    assert response.status_code == 200

    db = TestingSessionLocal()
    try:
        profile = db.query(UserProfile).join(User, UserProfile.user_id == User.id).filter(User.email == "test@example.com").first()
        assert profile.master_cv_structured["personal_info"]["title"] == "Platform Engineer"
    finally:
        db.close()
```

- [ ] **Step 4: Run the update test to verify it fails**

Run:
```bash
pytest src/backend/tests/test_profile_master_cv_structured.py::test_update_profile_saves_master_cv_structured -v
```

Expected: FAIL because `ProfileUpdate` and `update_profile()` do not support `master_cv_structured` yet.

- [ ] **Step 5: Implement minimal backend support for structured storage**

In `src/backend/app/database/sql_models.py`, extend `UserProfile`:

```python
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, JSON, Date, Boolean

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
    master_cv_structured = Column(JSON, nullable=True)
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
    master_cv_structured: Optional[dict[str, Any]] = None
```

In `src/backend/app/routers/profile.py`, save the new field:

```python
if data.master_cv_structured is not None:
    profile.master_cv_structured = data.master_cv_structured
```

In `src/backend/app/main.py`, extend the startup schema patch:

```python
def ensure_profile_master_cv_columns():
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("user_profiles")}

    with engine.begin() as connection:
        if "master_cv_text" not in columns:
            connection.execute(text("ALTER TABLE user_profiles ADD COLUMN master_cv_text TEXT NULL"))
        if "master_cv_structured" not in columns:
            connection.execute(text("ALTER TABLE user_profiles ADD COLUMN master_cv_structured JSON NULL"))
```
```

Call it in `lifespan()` before `seed_admin()`.

- [ ] **Step 6: Run the structured profile tests to verify they pass**

Run:
```bash
pytest src/backend/tests/test_profile_master_cv_structured.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/backend/app/database/sql_models.py src/backend/app/models.py src/backend/app/routers/profile.py src/backend/app/main.py src/backend/tests/test_profile_master_cv_structured.py
git commit -m "feat: store structured master cv in profile"
```

---

### Task 2: Add a parse-only route that normalizes raw CV text into `CVMakeoverData`

**Files:**
- Create: `src/backend/tests/test_cv_parse_master_cv_route.py`
- Modify: `src/backend/app/models.py:75-90`
- Modify: `src/backend/app/routers/cv.py:68-190`

- [ ] **Step 1: Write the failing parse-only route test**

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import cv
from app.routers.cv import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_post_parse_master_cv_returns_valid_structured_cv(monkeypatch):
    monkeypatch.setattr(
        cv,
        "call_ai_chat",
        lambda **kwargs: '''
        {
          "analysis_feedback": {"strengths": [], "weaknesses": [], "overall_score": 0},
          "personal_info": {"name": "Test User", "title": "Backend Engineer", "email": "", "phone": "", "linkedin": "", "location": "", "summary": ""},
          "skills": ["Python", "FastAPI"],
          "experience": [],
          "education": [],
          "projects": []
        }
        ''',
    )

    response = client.post(
        "/api/cv/parse-master-cv",
        json={"cv_text": "Python FastAPI Redis CV text"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["cv_data"]["personal_info"]["name"] == "Test User"
    assert payload["cv_data"]["skills"] == ["Python", "FastAPI"]
```

- [ ] **Step 2: Run the parse-only route test to verify it fails**

Run:
```bash
pytest src/backend/tests/test_cv_parse_master_cv_route.py::test_post_parse_master_cv_returns_valid_structured_cv -v
```

Expected: FAIL because `/api/cv/parse-master-cv` does not exist yet.

- [ ] **Step 3: Add the request model for parse-only normalization**

In `src/backend/app/models.py`, add:

```python
class MasterCVParseRequest(BaseModel):
    cv_text: str
```

- [ ] **Step 4: Implement the minimal parse-only route**

In `src/backend/app/routers/cv.py`, add a narrow route that reuses the existing parser path:

```python
@router.post("/api/cv/parse-master-cv")
async def parse_master_cv(request: models.MasterCVParseRequest):
    cv_text = request.cv_text.strip()
    if not cv_text:
        raise HTTPException(status_code=400, detail="CV text is required.")

    messages = [
        {"role": "system", "content": CV_JSON_SYSTEM_PROMPT + CV_INDUSTRY_TONES["tech"]},
        {"role": "user", "content": f"Đây là nội dung CV cần được chuẩn hóa thành JSON có cấu trúc:\n\n{cv_text}"},
    ]

    result = call_ai_chat(
        messages=messages,
        model="gpt-4.1",
        temperature=0.3,
        response_format={"type": "json_object"},
        timeout=120,
    )

    cv_data = parse_and_validate_cv(result)
    return {"cv_data": cv_data}
```

- [ ] **Step 5: Run the parse-only route test to verify it passes**

Run:
```bash
pytest src/backend/tests/test_cv_parse_master_cv_route.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/backend/app/models.py src/backend/app/routers/cv.py src/backend/tests/test_cv_parse_master_cv_route.py
git commit -m "feat: add parse-only master cv normalization route"
```

---

### Task 3: Add frontend API helpers for structured Master CV parsing

**Files:**
- Modify: `src/frontend/services/api.ts:185-215`

- [ ] **Step 1: Add the failing usage target by defining the new helper API**

Target helper:

```ts
export const parseMasterCV = async (cvText: string) => {
  const res = await apiRequest(`${API_URL}/cv/parse-master-cv`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cv_text: cvText }),
  });
  return res.json();
};
```

Use later in the profile page so the build fails until the profile UI is updated.

- [ ] **Step 2: Run frontend build after wiring the call site later to verify it fails first**

Run:
```bash
npm --prefix src/frontend run build
```

Expected: FAIL if the profile page references `parseMasterCV` before this helper exists.

- [ ] **Step 3: Implement the helper minimally**

Add to `src/frontend/services/api.ts`:

```ts
export const parseMasterCV = async (cvText: string) => {
  const res = await apiRequest(`${API_URL}/cv/parse-master-cv`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cv_text: cvText }),
  });
  return res.json();
};
```

- [ ] **Step 4: Re-run the frontend build once Task 4 is wired**

Run:
```bash
npm --prefix src/frontend run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/frontend/services/api.ts
git commit -m "feat: add structured master cv parse helper"
```

---

### Task 4: Upgrade the profile page from raw-only to raw + structured Master CV

**Files:**
- Modify: `src/frontend/app/profile/page.tsx:31-460`
- Modify: `src/frontend/services/api.ts`

- [ ] **Step 1: Add failing UI behavior for structured parse state**

Add target local state in `profile/page.tsx`:

```ts
const [extractingCv, setExtractingCv] = useState(false);
const [parsingCv, setParsingCv] = useState(false);
const [cvInputMode, setCvInputMode] = useState<"upload" | "paste">("upload");
const [masterCvParseError, setMasterCvParseError] = useState<string | null>(null);
```

The page should reference `info.master_cv_structured` and `parseMasterCV()` before wiring is complete so the build initially fails or type-checking reveals missing pieces.

- [ ] **Step 2: Run frontend build to verify failure before full wiring**

Run:
```bash
npm --prefix src/frontend run build
```

Expected: FAIL until all state/imports/UI are wired.

- [ ] **Step 3: Implement the raw + structured profile flow minimally**

Update upload handling so it extracts raw text and immediately parses it:

```ts
const handleMasterCvUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
  const file = e.target.files?.[0];
  if (!file) return;

  setExtractingCv(true);
  setMasterCvParseError(null);
  try {
    const raw = await extractCVText(file);
    const rawText = raw.extracted_text || "";
    setInfo((prev: any) => ({ ...prev, master_cv_text: rawText }));

    setParsingCv(true);
    const parsed = await parseMasterCV(rawText);
    setInfo((prev: any) => ({
      ...prev,
      master_cv_text: rawText,
      master_cv_structured: parsed.cv_data || null,
    }));
  } catch {
    setMasterCvParseError("Không thể chuẩn hóa CV này thành dữ liệu có cấu trúc.");
  } finally {
    setExtractingCv(false);
    setParsingCv(false);
    e.target.value = "";
  }
};
```

For pasted text, add an explicit parse action:

```ts
const handleParseMasterCvText = async () => {
  const rawText = (info.master_cv_text || "").trim();
  if (!rawText) return;

  setParsingCv(true);
  setMasterCvParseError(null);
  try {
    const parsed = await parseMasterCV(rawText);
    setInfo((prev: any) => ({
      ...prev,
      master_cv_structured: parsed.cv_data || null,
    }));
  } catch {
    setMasterCvParseError("Không thể chuẩn hóa CV này thành dữ liệu có cấu trúc.");
  } finally {
    setParsingCv(false);
  }
};
```

Add a lightweight structured summary:

```tsx
{info.master_cv_structured && (
  <div className="mt-4 rounded-2xl border border-theme-border bg-theme-secondary/50 p-4 space-y-2">
    <div className="text-sm font-bold text-white">Structured CV Summary</div>
    <div className="text-sm text-theme-text-secondary">
      {info.master_cv_structured.personal_info?.name || "Unnamed profile"}
      {info.master_cv_structured.personal_info?.title ? ` — ${info.master_cv_structured.personal_info.title}` : ""}
    </div>
    <div className="text-sm text-theme-text-secondary">
      Top skills: {(info.master_cv_structured.skills || []).slice(0, 5).join(", ") || "None detected"}
    </div>
    <div className="text-sm text-theme-text-secondary">
      Experience items: {(info.master_cv_structured.experience || []).length} · Projects: {(info.master_cv_structured.projects || []).length}
    </div>
  </div>
)}
```

Do not replace the existing profile save button. Saving still goes through `updateProfileInfo(info)`.

- [ ] **Step 4: Run the frontend build to verify it passes**

Run:
```bash
npm --prefix src/frontend run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/frontend/app/profile/page.tsx src/frontend/services/api.ts
git commit -m "feat: store structured master cv in profile"
```

---

### Task 5: Make interview setup consume structured Master CV by default

**Files:**
- Modify: `src/frontend/app/interview/page.tsx:73-210`
- Modify: `src/frontend/components/Interview/SetupForm.tsx:11-90`
- Modify: `src/frontend/services/api.ts`

- [ ] **Step 1: Add the failing bootstrap target for structured context input**

Introduce a helper to convert structured CV into stable text for the existing context API:

```ts
const structuredCvToInterviewText = (cv: any) => {
  const personal = cv?.personal_info || {};
  const skills = Array.isArray(cv?.skills) ? cv.skills.join(", ") : "";
  const experience = Array.isArray(cv?.experience)
    ? cv.experience.map((item: any) => `${item.role || ""} at ${item.company || ""}: ${(item.achievements || []).join("; ")}`).join("\n")
    : "";
  const projects = Array.isArray(cv?.projects)
    ? cv.projects.map((item: any) => `${item.name || ""}: ${item.description || ""}`).join("\n")
    : "";

  return [
    personal.name,
    personal.title,
    personal.summary,
    skills,
    experience,
    projects,
  ].filter(Boolean).join("\n\n");
};
```

- [ ] **Step 2: Run frontend build to verify failure before full wiring if references are incomplete**

Run:
```bash
npm --prefix src/frontend run build
```

Expected: FAIL until the setup flow is fully wired.

- [ ] **Step 3: Implement structured bootstrap path**

In `interview/page.tsx`, replace raw-text-first bootstrap with structured-first bootstrap:

```ts
const masterCvStructured = myProfileData?.info?.master_cv_structured || null;
const hasStructuredMasterCv = Boolean(masterCvStructured);

const bootstrapInterviewContext = useCallback(async () => {
  if (!hasStructuredMasterCv || !hasJd) {
    persistInterviewContext(null);
    setInterviewContextError(null);
    return true;
  }

  setIsBootstrappingContext(true);
  setInterviewContextError(null);

  try {
    const cvText = structuredCvToInterviewText(masterCvStructured);
    const result = await buildInterviewContext(cvText, config.jd.trim());
    persistInterviewContext((result?.interview_context as Record<string, unknown> | null) || null);
    return true;
  } catch {
    persistInterviewContext(null);
    setInterviewContextError("Could not prepare interview context from your structured Master CV.");
    return false;
  } finally {
    setIsBootstrappingContext(false);
  }
}, [config.jd, hasJd, hasStructuredMasterCv, masterCvStructured, persistInterviewContext]);
```

In `SetupForm.tsx`, adjust the status messaging to reflect structured readiness:

```tsx
<div className="text-sm text-theme-text-secondary rounded-xl bg-theme-secondary/60 border border-theme-border px-4 py-3">
  {masterCvStatus || (masterCvAvailable
    ? "Using your structured Master CV as the default interview context source."
    : "No saved Master CV yet — interview will use JD only.")}
</div>
```

Make sure `masterCvAvailable` means **structured CV available**, not raw text only.

- [ ] **Step 4: Run the frontend build to verify it passes**

Run:
```bash
npm --prefix src/frontend run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/frontend/app/interview/page.tsx src/frontend/components/Interview/SetupForm.tsx src/frontend/services/api.ts
git commit -m "feat: bootstrap interview context from structured master cv"
```

---

### Task 6: Final verification for raw + structured Master CV

**Files:**
- Verify only

- [ ] **Step 1: Run backend tests for structured Master CV**

Run:
```bash
pytest src/backend/tests/test_profile_master_cv.py src/backend/tests/test_profile_master_cv_structured.py src/backend/tests/test_cv_extract_text_route.py src/backend/tests/test_cv_parse_master_cv_route.py src/backend/tests/test_interview_context.py -v
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
3. Upload PDF/DOCX or paste raw CV text
4. Confirm raw text appears
5. Confirm structured summary appears after parsing
6. Save profile
7. Refresh and confirm both raw and structured data persist
8. Open `/interview`
9. Enter a JD
10. Confirm setup reports structured Master CV usage
11. Start interview and confirm session uses interview context built from the structured CV form

Expected:
- structured CV parsing succeeds
- structured summary persists
- interview bootstrap depends on the structured form, not raw text alone

- [ ] **Step 4: Commit**

```bash
git add src/backend/app/database/sql_models.py src/backend/app/models.py src/backend/app/main.py src/backend/app/routers/profile.py src/backend/app/routers/cv.py src/backend/tests/test_profile_master_cv.py src/backend/tests/test_profile_master_cv_structured.py src/backend/tests/test_cv_extract_text_route.py src/backend/tests/test_cv_parse_master_cv_route.py src/frontend/services/api.ts src/frontend/app/profile/page.tsx src/frontend/app/interview/page.tsx src/frontend/components/Interview/SetupForm.tsx
git commit -m "feat: add structured master cv pipeline"
```

---

## Self-review against spec

### Spec coverage
- Raw + structured storage: covered by Task 1.
- Immediate parse after upload/paste: covered by Tasks 2 and 4.
- Reuse of `CVMakeoverData`, `parse_and_validate_cv`, and `extract_text_from_cv`: covered by Tasks 2 and 4.
- Interview setup consumes structured form: covered by Task 5.
- Existing `sessionStorage` context flow reused: covered by Task 5.

### Placeholder scan
- No TBD/TODO placeholders remain.
- Each task includes exact file paths, code, and commands.
- Every test-first step includes a RED verification command.

### Type consistency
- `master_cv_text` and `master_cv_structured` are used consistently across backend storage, profile API, profile UI, and interview bootstrap.
- `cv_data` is used consistently as the structured CV response shape from the parse-only route.

---

Plan complete and saved to `docs/superpowers/plans/2026-05-15-speakcv-profile-master-cv-structured.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**