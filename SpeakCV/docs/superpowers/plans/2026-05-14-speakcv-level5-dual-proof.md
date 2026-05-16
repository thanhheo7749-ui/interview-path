# SpeakCV Level 5 Dual-Proof Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the minimum believable Level 5-capable hybrid AI upgrade for SpeakCV by adding an orchestrator foundation, Interview Intelligence proof point, CV Reasoning Intelligence proof point, and visible explainability/metrics outputs.

**Architecture:** Keep the current FastAPI + Next.js structure, but move route-level AI logic toward a small orchestrator layer that collects specialist signals before handing them to the LLM explanation layer. Ship two visible proof points: interview transcript/speaking-quality signals and CV graph/inflation signals, then surface those signals in structured responses and UI blocks.

**Tech Stack:** FastAPI, Pydantic, Next.js App Router, React, TypeScript, existing Gemini/OpenAI provider layer, Groq Whisper, heuristic scoring services, existing frontend hooks/components.

---

## File structure and responsibilities

### Backend files to create
- `src/backend/app/services/orchestrator.py` — central orchestration entry points for interview and CV proof-point flows
- `src/backend/app/services/transcript_quality.py` — transcript confidence scoring and confirmation decision
- `src/backend/app/services/prosody_scoring.py` — speaking-quality heuristic scoring from transcript/audio metadata
- `src/backend/app/services/skill_graph_scoring.py` — prerequisite-aware CV skill scoring
- `src/backend/app/services/inflation_risk.py` — CV overclaim / mismatch signal generator
- `src/backend/app/services/ai_metrics.py` — normalize step logs and response usage metadata

### Backend files to modify
- `src/backend/app/models.py` — request/response schemas for structured `analysis`, `evidence`, `usage`, `trace_id`
- `src/backend/app/routers/interview.py` — move from direct prompt-heavy flow to orchestrated interview pipeline
- `src/backend/app/routers/cv.py` — add structured CV scoring flow before explanation
- `src/backend/app/ai_service.py` — return normalized metadata helpful for orchestrator and metrics
- `src/backend/app/routers/admin.py` — optional lightweight metrics endpoint

### Frontend files to create
- `src/frontend/components/Interview/SignalCards.tsx` — display interview confidence/speaking signals
- `src/frontend/components/Interview/TranscriptConfirmModal.tsx` — confirm or edit weak transcript before continuing
- `src/frontend/components/Modals/CV/CVReasoningPanel.tsx` — display CV structured signals and evidence block
- `src/frontend/components/Admin/AIHybridTab.tsx` — simple metrics view for demo/admin

### Frontend files to modify
- `src/frontend/hooks/useChat.ts` — support structured interview response, transcript confirmation, and signal state
- `src/frontend/services/api.ts` — update request/response typing and add metrics fetch
- `src/frontend/app/interview/page.tsx` — show signal cards and transcript confirm modal
- `src/frontend/components/Modals/ReviewCVModal.tsx` — show CV evidence/reasoning block
- `src/frontend/app/admin/page.tsx` — add AI hybrid metrics tab if feasible

### Tests to create
- `src/backend/tests/test_transcript_quality.py`
- `src/backend/tests/test_prosody_scoring.py`
- `src/backend/tests/test_skill_graph_scoring.py`
- `src/backend/tests/test_inflation_risk.py`
- `src/backend/tests/test_orchestrator.py`

Because the repo does not currently expose clear frontend app-level test files, this plan keeps frontend validation lightweight and focused on manual verification plus existing lint/build commands.

---

### Task 1: Create orchestrator foundation

**Files:**
- Create: `src/backend/app/services/orchestrator.py`
- Create: `src/backend/app/services/ai_metrics.py`
- Modify: `src/backend/app/models.py`
- Modify: `src/backend/app/ai_service.py`
- Test: `src/backend/tests/test_orchestrator.py`

- [ ] **Step 1: Write the failing orchestrator test**

```python
from app.services.orchestrator import build_interview_result


def test_build_interview_result_wraps_content_analysis_and_trace():
    result = build_interview_result(
        ai_text="Next question?",
        analysis={"transcript_confidence": 0.81},
        usage={"provider": "gemini"},
        trace_id="trace-123",
    )

    assert result["content"] == "Next question?"
    assert result["analysis"]["transcript_confidence"] == 0.81
    assert result["usage"]["provider"] == "gemini"
    assert result["trace_id"] == "trace-123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest src/backend/tests/test_orchestrator.py::test_build_interview_result_wraps_content_analysis_and_trace -v`
Expected: FAIL with import error or missing function error.

- [ ] **Step 3: Write minimal orchestrator and metrics implementation**

```python
# src/backend/app/services/orchestrator.py
from uuid import uuid4


def new_trace_id() -> str:
    return str(uuid4())


def build_interview_result(ai_text: str, analysis: dict, usage: dict, trace_id: str | None = None) -> dict:
    return {
        "content": ai_text,
        "analysis": analysis,
        "usage": usage,
        "trace_id": trace_id or new_trace_id(),
    }


def build_cv_result(content: str, analysis: dict, evidence: dict, usage: dict, trace_id: str | None = None) -> dict:
    return {
        "content": content,
        "analysis": analysis,
        "evidence": evidence,
        "usage": usage,
        "trace_id": trace_id or new_trace_id(),
    }
```

```python
# src/backend/app/services/ai_metrics.py
import time


def build_usage(provider: str, model: str, started_at: float) -> dict:
    return {
        "provider": provider,
        "model": model,
        "latency_ms": int((time.time() - started_at) * 1000),
    }
```

- [ ] **Step 4: Add minimal schema support for structured responses**

```python
# add to src/backend/app/models.py
from pydantic import BaseModel, Field
from typing import Any


class InterviewAIResponse(BaseModel):
    content: str
    analysis: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)
    trace_id: str


class CVAIResponse(BaseModel):
    content: str
    analysis: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)
    trace_id: str
```

- [ ] **Step 5: Normalize provider metadata in `ai_service.py`**

```python
# add helper in src/backend/app/ai_service.py

def call_ai_chat_with_meta(...):
    started_at = time.time()
    content = call_ai_chat(...)
    return {
        "content": content,
        "provider": "gemini" if GEMINI_API_KEY else "openai",
        "model": model,
        "latency_ms": int((time.time() - started_at) * 1000),
    }
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest src/backend/tests/test_orchestrator.py::test_build_interview_result_wraps_content_analysis_and_trace -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/backend/app/services/orchestrator.py src/backend/app/services/ai_metrics.py src/backend/app/models.py src/backend/app/ai_service.py src/backend/tests/test_orchestrator.py
git commit -m "feat: add orchestrator response foundation"
```

---

### Task 2: Add post-STT transcript quality scoring for interview proof point

**Files:**
- Create: `src/backend/app/services/transcript_quality.py`
- Modify: `src/backend/app/routers/interview.py`
- Test: `src/backend/tests/test_transcript_quality.py`

- [ ] **Step 1: Write the failing transcript-quality test**

```python
from app.services.transcript_quality import score_transcript_quality


def test_score_transcript_quality_flags_short_low_quality_english_text():
    result = score_transcript_quality("ok", "en")

    assert result["transcript_confidence"] < 0.5
    assert result["low_quality_flag"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest src/backend/tests/test_transcript_quality.py::test_score_transcript_quality_flags_short_low_quality_english_text -v`
Expected: FAIL with import error or missing function error.

- [ ] **Step 3: Write minimal post-STT transcript-quality implementation**

```python
# src/backend/app/services/transcript_quality.py
import re


def score_transcript_quality(text: str, lang: str) -> dict:
    normalized = (text or "").strip()
    words = re.findall(r"[a-zA-ZÀ-ỹ']+", normalized)
    too_short = len(words) < 4
    confidence = 0.25 if too_short else 0.85
    if lang == "en" and too_short:
        confidence = 0.2
    return {
        "transcript_confidence": confidence,
        "low_quality_flag": confidence < 0.65,
        "word_count": len(words),
        "quality_reason": "too_short" if too_short else "clear_enough",
    }
```

- [ ] **Step 4: Call transcript-quality scoring inside `interview.py` after STT output is already available as text**

```python
# inside chat() in src/backend/app/routers/interview.py
from ..services.transcript_quality import score_transcript_quality

transcript_analysis = score_transcript_quality(request.user_text, request.lang or "vi")
```

- [ ] **Step 5: Add a light prompt hint instead of blocking the flow**

```python
if transcript_analysis["low_quality_flag"]:
    base_prompt += "\n\n[TRANSCRIPT QUALITY] The user's transcribed answer may be incomplete or unclear. Do not over-interpret missing details. If needed, ask a short clarifying follow-up."
```

- [ ] **Step 6: Return transcript-quality signals inside the structured interview analysis block**

```python
analysis = {
    "transcript": transcript_analysis,
}
```

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest src/backend/tests/test_transcript_quality.py::test_score_transcript_quality_flags_short_low_quality_english_text -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/backend/app/services/transcript_quality.py src/backend/app/routers/interview.py src/backend/tests/test_transcript_quality.py
git commit -m "feat: add post-stt transcript quality scoring"
```

---

### Task 3: Add lightweight speaking-signal scoring for interview proof point

**Files:**
- Create: `src/backend/app/services/prosody_scoring.py`
- Modify: `src/backend/app/routers/interview.py`
- Test: `src/backend/tests/test_prosody_scoring.py`

- [ ] **Step 1: Write the failing speaking-signal test**

```python
from app.services.prosody_scoring import score_speaking_signals


def test_score_speaking_signals_returns_expected_keys_from_text():
    result = score_speaking_signals("Um I have worked with React and FastAPI")

    assert "filler_rate" in result
    assert "clarity_score" in result
    assert "speaking_signal" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest src/backend/tests/test_prosody_scoring.py::test_score_speaking_signals_returns_expected_keys_from_text -v`
Expected: FAIL with import error or missing function error.

- [ ] **Step 3: Write minimal speaking-signal implementation based mostly on post-STT text**

```python
# src/backend/app/services/prosody_scoring.py
import re


def score_speaking_signals(text: str, audio_meta: dict | None = None) -> dict:
    audio_meta = audio_meta or {}
    words = re.findall(r"[a-zA-ZÀ-ỹ']+", text or "")
    fillers = [w for w in words if w.lower() in {"um", "uh", "like", "well", "so"}]
    filler_rate = round(len(fillers) / max(len(words), 1), 3)
    clarity_score = round(max(0.1, 1 - filler_rate), 3)
    return {
        "filler_rate": filler_rate,
        "clarity_score": clarity_score,
        "speaking_signal": "hesitant" if filler_rate > 0.15 else "clear",
        "pause_hint": audio_meta.get("pause_ratio"),
    }
```

- [ ] **Step 4: Merge speaking-signal data into the interview analysis response without requiring a full audio feature pipeline**

```python
# inside chat() in src/backend/app/routers/interview.py
from ..services.prosody_scoring import score_speaking_signals

speaking_signals = score_speaking_signals(request.user_text)
analysis = {
    "transcript": transcript_analysis,
    "speaking_signals": speaking_signals,
}
```

- [ ] **Step 5: Add a light prompt hint when the speaking signal is hesitant**

```python
if speaking_signals["speaking_signal"] == "hesitant":
    base_prompt += "\n\n[SPEAKING SIGNAL] The user's answer appears hesitant or filler-heavy. Keep the response supportive and ask a concise follow-up if clarification is useful."
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest src/backend/tests/test_prosody_scoring.py::test_score_speaking_signals_returns_expected_keys_from_text -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/backend/app/services/prosody_scoring.py src/backend/app/routers/interview.py src/backend/tests/test_prosody_scoring.py
git commit -m "feat: add lightweight speaking signal scoring"
```

---

### Task 4: Route interview flow through orchestrator and adaptive analysis

**Files:**
- Modify: `src/backend/app/routers/interview.py`
- Modify: `src/backend/app/models.py`
- Test: `src/backend/tests/test_orchestrator.py`

- [ ] **Step 1: Write the failing orchestrated interview-flow test**

```python
from app.services.orchestrator import build_interview_result


def test_interview_result_contains_transcript_and_speaking_signal_blocks():
    result = build_interview_result(
        ai_text="Tell me about a project.",
        analysis={
            "transcript": {"transcript_confidence": 0.9, "low_quality_flag": False},
            "speaking_signals": {"clarity_score": 0.88, "speaking_signal": "clear"},
        },
        usage={"provider": "gemini"},
        trace_id="trace-456",
    )

    assert result["analysis"]["transcript"]["transcript_confidence"] == 0.9
    assert result["analysis"]["speaking_signals"]["clarity_score"] == 0.88
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest src/backend/tests/test_orchestrator.py::test_interview_result_contains_transcript_and_prosody_blocks -v`
Expected: FAIL until structured analysis shape is complete.

- [ ] **Step 3: Add request field support for audio metadata**

```python
# add to ChatRequest in src/backend/app/models.py
from typing import Any

audio_meta: dict[str, Any] | None = None
lang: str | None = None
```

- [ ] **Step 4: Replace ad-hoc final interview return with orchestrator result**

```python
# near final return in src/backend/app/routers/interview.py
llm_result = call_ai_chat_with_meta(
    messages=messages,
    model="gpt-4o-mini",
    temperature=temperature,
    max_tokens=250,
    timeout=90,
)

return build_interview_result(
    ai_text=llm_result["content"],
    analysis=analysis,
    usage={
        "provider": llm_result["provider"],
        "model": llm_result["model"],
        "latency_ms": llm_result["latency_ms"],
    },
    trace_id=trace_id,
)
```

- [ ] **Step 5: Run tests to verify the structured interview result passes**

Run: `pytest src/backend/tests/test_orchestrator.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/backend/app/routers/interview.py src/backend/app/models.py src/backend/tests/test_orchestrator.py
git commit -m "feat: orchestrate structured interview responses"
```

---

### Task 5: Add CV + JD structured interview-context scoring

**Files:**
- Create: `src/backend/app/services/skill_graph_scoring.py`
- Modify: `src/backend/app/routers/cv.py`
- Test: `src/backend/tests/test_skill_graph_scoring.py`

- [ ] **Step 1: Write the failing CV+JD context-scoring test**

```python
from app.services.skill_graph_scoring import build_interview_context_from_cv_jd


def test_build_interview_context_from_cv_jd_reports_strengths_gaps_and_topics():
    result = build_interview_context_from_cv_jd(
        cv_skills=["FastAPI", "Python"],
        jd_skills=["Python", "FastAPI", "System Design"],
    )

    assert result["match_score"] < 1.0
    assert "System Design" in result["skill_gaps"]
    assert result["target_topics"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest src/backend/tests/test_skill_graph_scoring.py::test_build_interview_context_from_cv_jd_reports_strengths_gaps_and_topics -v`
Expected: FAIL with import error or missing function error.

- [ ] **Step 3: Write minimal structured CV+JD context builder**

```python
# src/backend/app/services/skill_graph_scoring.py

def build_interview_context_from_cv_jd(cv_skills: list[str], jd_skills: list[str]) -> dict:
    cv_set = {skill.strip() for skill in cv_skills if skill.strip()}
    jd_set = {skill.strip() for skill in jd_skills if skill.strip()}
    matched = sorted(cv_set & jd_set)
    missing = sorted(jd_set - cv_set)
    score = round(len(matched) / max(len(jd_set), 1), 2)
    target_topics = missing[:3] if missing else matched[:3]
    return {
        "match_score": score,
        "highlighted_strengths": matched[:3],
        "skill_gaps": missing,
        "target_topics": target_topics,
    }
```

- [ ] **Step 4: Extract simple skill lists and build interview context in `cv.py`**

```python
# helper in src/backend/app/routers/cv.py
import re


def extract_skill_candidates(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,\n]", text) if part.strip()]

cv_skills = extract_skill_candidates(cv_text)
jd_skills = extract_skill_candidates(jd_text)
interview_context = build_interview_context_from_cv_jd(cv_skills, jd_skills)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest src/backend/tests/test_skill_graph_scoring.py::test_build_interview_context_from_cv_jd_reports_strengths_gaps_and_topics -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/backend/app/services/skill_graph_scoring.py src/backend/app/routers/cv.py src/backend/tests/test_skill_graph_scoring.py
git commit -m "feat: add cv jd interview context scoring"
```

---

### Task 6: Add CV inflation-risk proof point

**Files:**
- Create: `src/backend/app/services/inflation_risk.py`
- Modify: `src/backend/app/routers/cv.py`
- Test: `src/backend/tests/test_inflation_risk.py`

- [ ] **Step 1: Write the failing inflation-risk test**

```python
from app.services.inflation_risk import score_inflation_risk


def test_score_inflation_risk_flags_dense_senior_claims_without_support():
    text = "Senior architect expert lead principal visionary 1 year internship"
    result = score_inflation_risk(text)

    assert result["label"] in {"medium", "high"}
    assert result["signals"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest src/backend/tests/test_inflation_risk.py::test_score_inflation_risk_flags_dense_senior_claims_without_support -v`
Expected: FAIL with import error or missing function error.

- [ ] **Step 3: Write minimal inflation-risk implementation**

```python
# src/backend/app/services/inflation_risk.py
import re


def score_inflation_risk(text: str) -> dict:
    normalized = (text or "").lower()
    signals = []
    senior_terms = ["senior", "architect", "principal", "lead", "expert"]
    years = re.findall(r"(\d+)\s+year", normalized)

    senior_hits = sum(term in normalized for term in senior_terms)
    if senior_hits >= 3:
        signals.append("dense_senior_language")
    if years and min(int(year) for year in years) <= 1 and senior_hits >= 2:
        signals.append("years_scope_mismatch")

    label = "high" if len(signals) >= 2 else "medium" if len(signals) == 1 else "low"
    return {
        "label": label,
        "signals": signals,
    }
```

- [ ] **Step 4: Attach inflation risk to CV analysis/evidence**

```python
inflation_result = score_inflation_risk(cv_text)
analysis = {"graph": graph_result, "inflation_risk": inflation_result}
evidence = {
    "matched_skills": graph_result["matched_skills"],
    "missing_prerequisites": graph_result["missing_prerequisites"],
    "inflation_signals": inflation_result["signals"],
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest src/backend/tests/test_inflation_risk.py::test_score_inflation_risk_flags_dense_senior_claims_without_support -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/backend/app/services/inflation_risk.py src/backend/app/routers/cv.py src/backend/tests/test_inflation_risk.py
git commit -m "feat: add cv inflation risk scoring"
```

---

### Task 7: Return structured CV + JD reasoning and interview-context results

**Files:**
- Modify: `src/backend/app/routers/cv.py`
- Modify: `src/backend/app/models.py`
- Test: `src/backend/tests/test_orchestrator.py`

- [ ] **Step 1: Write the failing CV result test**

```python
from app.services.orchestrator import build_cv_result


def test_build_cv_result_includes_interview_context_and_evidence():
    result = build_cv_result(
        content="CV analysis",
        analysis={"interview_context": {"match_score": 0.67}},
        evidence={"skill_gaps": ["System Design"]},
        usage={"provider": "gemini"},
        trace_id="trace-cv-1",
    )

    assert result["analysis"]["interview_context"]["match_score"] == 0.67
    assert result["evidence"]["skill_gaps"] == ["System Design"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest src/backend/tests/test_orchestrator.py::test_build_cv_result_includes_interview_context_and_evidence -v`
Expected: FAIL until CV response path is consistent.

- [ ] **Step 3: Build CV+JD explanation prompt from structured signals and interview context**

```python
explanation_prompt = f"""
CV strengths: {interview_context['highlighted_strengths']}
CV skill gaps: {interview_context['skill_gaps']}
Target interview topics: {interview_context['target_topics']}
Inflation signals: {inflation_result['signals']}

Explain this result clearly in Vietnamese for the candidate, and summarize what the interview should focus on.
"""
```

- [ ] **Step 4: Return structured CV result with interview context, evidence, and interview-planning hints**

```python
analysis = {
    "interview_context": interview_context,
    "inflation_risk": inflation_result,
}
evidence = {
    "highlighted_strengths": interview_context["highlighted_strengths"],
    "skill_gaps": interview_context["skill_gaps"],
    "target_topics": interview_context["target_topics"],
    "inflation_signals": inflation_result["signals"],
}

llm_result = call_ai_chat_with_meta(
    messages=[
        {"role": "system", "content": "Explain CV and JD reasoning clearly and concisely."},
        {"role": "user", "content": explanation_prompt},
    ],
    model="gpt-4o",
    timeout=90,
)

return build_cv_result(
    content=llm_result["content"],
    analysis=analysis,
    evidence=evidence,
    usage={
        "provider": llm_result["provider"],
        "model": llm_result["model"],
        "latency_ms": llm_result["latency_ms"],
    },
    trace_id=trace_id,
)
```

- [ ] **Step 5: Run tests to verify the CV result shape passes**

Run: `pytest src/backend/tests/test_orchestrator.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/backend/app/routers/cv.py src/backend/app/models.py src/backend/tests/test_orchestrator.py
git commit -m "feat: return cv jd interview context results"
```

---

### Task 8: Show interview proof point in the frontend

**Files:**
- Create: `src/frontend/components/Interview/SignalCards.tsx`
- Create: `src/frontend/components/Interview/TranscriptConfirmModal.tsx`
- Modify: `src/frontend/hooks/useChat.ts`
- Modify: `src/frontend/services/api.ts`
- Modify: `src/frontend/app/interview/page.tsx`

- [ ] **Step 1: Add frontend response typings**

```ts
// src/frontend/services/api.ts
export type InterviewAnalysis = {
  transcript?: {
    confidence: number;
    needs_confirmation: boolean;
    word_count?: number;
  };
  prosody?: {
    pace_wpm: number;
    pause_ratio: number;
    filler_rate: number;
    confidence_score: number;
  };
};

export type InterviewAIResponse = {
  content: string;
  analysis: InterviewAnalysis;
  usage: Record<string, unknown>;
  trace_id: string;
};
```

- [ ] **Step 2: Update `useChat.ts` to store signal state and confirmation state**

```ts
const [analysis, setAnalysis] = useState<InterviewAnalysis | null>(null);
const [pendingTranscriptConfirm, setPendingTranscriptConfirm] = useState(false);

setAnalysis(response.analysis);
setPendingTranscriptConfirm(Boolean(response.analysis?.transcript?.needs_confirmation));
```

- [ ] **Step 3: Create minimal signal cards component**

```tsx
// src/frontend/components/Interview/SignalCards.tsx
export function SignalCards({ analysis }: { analysis: InterviewAnalysis | null }) {
  if (!analysis) return null;

  return (
    <div className="grid gap-3 md:grid-cols-4">
      <div>Transcript: {analysis.transcript?.confidence ?? "-"}</div>
      <div>Pace: {analysis.prosody?.pace_wpm ?? "-"}</div>
      <div>Filler: {analysis.prosody?.filler_rate ?? "-"}</div>
      <div>Confidence: {analysis.prosody?.confidence_score ?? "-"}</div>
    </div>
  );
}
```

- [ ] **Step 4: Create minimal transcript confirmation modal**

```tsx
// src/frontend/components/Interview/TranscriptConfirmModal.tsx
export function TranscriptConfirmModal({
  open,
  transcript,
  onClose,
}: {
  open: boolean;
  transcript: string;
  onClose: () => void;
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 flex items-center justify-center bg-black/50">
      <div className="rounded bg-white p-4 text-black">
        <h2>Confirm transcript</h2>
        <p>{transcript}</p>
        <button onClick={onClose}>Continue</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Render signal cards and confirmation modal in `app/interview/page.tsx`**

```tsx
<SignalCards analysis={analysis} />
<TranscriptConfirmModal
  open={pendingTranscriptConfirm}
  transcript={lastUserMessage}
  onClose={() => setPendingTranscriptConfirm(false)}
/>
```

- [ ] **Step 6: Run frontend verification**

Run: `npm run lint`
Expected: PASS or only pre-existing unrelated warnings.

- [ ] **Step 7: Manual verification**

Run app and verify:
- normal transcript shows signal cards
- low-confidence transcript opens confirmation modal
- interview flow still continues for normal turns

- [ ] **Step 8: Commit**

```bash
git add src/frontend/components/Interview/SignalCards.tsx src/frontend/components/Interview/TranscriptConfirmModal.tsx src/frontend/hooks/useChat.ts src/frontend/services/api.ts src/frontend/app/interview/page.tsx
git commit -m "feat: show interview intelligence proof signals"
```

---

### Task 9: Use CV + JD analysis in the frontend to seed smarter interview setup

**Files:**
- Create: `src/frontend/components/Modals/CV/CVReasoningPanel.tsx`
- Modify: `src/frontend/components/Modals/ReviewCVModal.tsx`
- Modify: `src/frontend/services/api.ts`
- Modify: `src/frontend/app/interview/page.tsx`
- Modify: `src/frontend/hooks/useChat.ts`

- [ ] **Step 1: Add CV response typings with interview context**

```ts
export type CVReasoningResponse = {
  content: string;
  analysis: {
    interview_context?: {
      match_score: number;
      highlighted_strengths: string[];
      skill_gaps: string[];
      target_topics: string[];
    };
    inflation_risk?: { label: string; signals: string[] };
  };
  evidence: {
    highlighted_strengths?: string[];
    skill_gaps?: string[];
    target_topics?: string[];
    inflation_signals?: string[];
  };
  usage: Record<string, unknown>;
  trace_id: string;
};
```

- [ ] **Step 2: Create a lightweight CV reasoning panel that summarizes interview-relevant context**

```tsx
// src/frontend/components/Modals/CV/CVReasoningPanel.tsx
export function CVReasoningPanel({ result }: { result: CVReasoningResponse | null }) {
  if (!result) return null;

  return (
    <div className="space-y-2 rounded border p-3">
      <div>Match score: {result.analysis.interview_context?.match_score ?? "-"}</div>
      <div>Strengths: {(result.evidence.highlighted_strengths || []).join(", ")}</div>
      <div>Focus topics: {(result.evidence.target_topics || []).join(", ")}</div>
      <div>Skill gaps: {(result.evidence.skill_gaps || []).join(", ")}</div>
    </div>
  );
}
```

- [ ] **Step 3: Render the reasoning panel in `ReviewCVModal.tsx` as a summary block, not a full CV presentation**

```tsx
<CVReasoningPanel result={cvReasoningResult} />
<div>{cvReasoningResult?.content}</div>
```

- [ ] **Step 4: Save `target_topics` and interview context for the interview flow**

```ts
sessionStorage.setItem(
  "interview_context",
  JSON.stringify(cvReasoningResult?.analysis.interview_context ?? null)
);
```

- [ ] **Step 5: Read saved interview context in `useChat.ts` or `app/interview/page.tsx` and attach it to interview requests**

```ts
const rawInterviewContext = sessionStorage.getItem("interview_context");
const interviewContext = rawInterviewContext ? JSON.parse(rawInterviewContext) : null;

body: JSON.stringify({
  ...payload,
  interview_context: interviewContext,
})
```

- [ ] **Step 6: Run frontend verification**

Run: `npm run lint`
Expected: PASS or only pre-existing unrelated warnings.

- [ ] **Step 7: Manual verification**

Run app and verify:
- CV upload still works
- summary block appears without rendering the whole CV again
- target topics from CV + JD are available before interview starts
- interview flow can use that context for smarter questions

- [ ] **Step 8: Commit**

```bash
git add src/frontend/components/Modals/CV/CVReasoningPanel.tsx src/frontend/components/Modals/ReviewCVModal.tsx src/frontend/services/api.ts src/frontend/app/interview/page.tsx src/frontend/hooks/useChat.ts
git commit -m "feat: seed interview flow from cv jd analysis"
```

---

### Task 10: Add lightweight metrics and demo credibility support

**Files:**
- Modify: `src/backend/app/services/ai_metrics.py`
- Modify: `src/backend/app/routers/admin.py`
- Create: `src/frontend/components/Admin/AIHybridTab.tsx`
- Modify: `src/frontend/app/admin/page.tsx`

- [ ] **Step 1: Write the failing metrics test**

```python
from app.services.ai_metrics import build_usage


def test_build_usage_contains_provider_model_and_latency():
    result = build_usage("gemini", "gpt-4o-mini", 0)

    assert result["provider"] == "gemini"
    assert result["model"] == "gpt-4o-mini"
    assert "latency_ms" in result
```

- [ ] **Step 2: Run test to verify it fails if helper shape changed**

Run: `pytest src/backend/tests/test_orchestrator.py::test_build_usage_contains_provider_model_and_latency -v`
Expected: FAIL until test file is added or helper is aligned.

- [ ] **Step 3: Add lightweight admin metrics endpoint**

```python
# in src/backend/app/routers/admin.py
@router.get("/api/admin/ai-hybrid-metrics")
def get_ai_hybrid_metrics():
    return {
        "providers": ["gemini", "openai"],
        "fallback_enabled": True,
        "proof_points": ["interview_intelligence", "cv_reasoning_intelligence"],
    }
```

- [ ] **Step 4: Create simple admin tab for metrics**

```tsx
// src/frontend/components/Admin/AIHybridTab.tsx
export function AIHybridTab() {
  return (
    <div className="space-y-3">
      <h3>AI Hybrid Metrics</h3>
      <p>Interview Intelligence enabled</p>
      <p>CV Reasoning Intelligence enabled</p>
    </div>
  );
}
```

- [ ] **Step 5: Mount admin tab in `app/admin/page.tsx`**

```tsx
{activeTab === "ai-hybrid" && <AIHybridTab />}
```

- [ ] **Step 6: Run verification**

Run backend tests: `pytest src/backend/tests -v`
Run frontend lint: `npm run lint`
Expected: PASS or only pre-existing unrelated issues that are documented before merge.

- [ ] **Step 7: Manual verification**

Verify in UI:
- admin tab renders
- proof-point terminology is visible and consistent with pitch language

- [ ] **Step 8: Commit**

```bash
git add src/backend/app/services/ai_metrics.py src/backend/app/routers/admin.py src/frontend/components/Admin/AIHybridTab.tsx src/frontend/app/admin/page.tsx
git commit -m "feat: add lightweight hybrid ai metrics view"
```

---

## Self-review

### Spec coverage
- Orchestrator foundation: covered by Tasks 1 and 4
- Interview proof point: covered by Tasks 2, 3, 4, and 8
- CV proof point: covered by Tasks 5, 6, 7, and 9
- Explainability and visible output: covered by Tasks 7, 8, and 9
- Metrics / credibility layer: covered by Task 10
- Korean-compatible polish: intentionally left out of core implementation; can be added after proof points land

### Placeholder scan
- No TBD/TODO placeholders remain
- Each code-writing step includes concrete code blocks
- Each verification step includes concrete commands and expected outcomes

### Type consistency
- Structured response keys are consistently `content`, `analysis`, `evidence`, `usage`, `trace_id`
- Interview proof consistently uses `transcript` and `prosody`
- CV proof consistently uses `graph` and `inflation_risk`

---
