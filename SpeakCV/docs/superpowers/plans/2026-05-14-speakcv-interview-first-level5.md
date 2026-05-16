# SpeakCV Interview-First Level 5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an Interview-first Level 5-capable AI Interview Prep Coach where CV and JD act as context feeders, the live interview loop stays fast, and the strongest product value comes from question planning, answer evaluation, and coaching quality.

**Architecture:** Split the interview system into three latency tiers: pre-interview context building, low-latency per-turn evaluation, and deeper post-interview coaching synthesis. Keep the live path lightweight by using post-STT transcript signals, text-based speaking signals, and structured turn evaluation instead of heavy analysis at every turn.

**Tech Stack:** FastAPI, Pydantic, Next.js App Router, React, TypeScript, existing Gemini/OpenAI provider layer, Groq Whisper, current interview router, lightweight backend scoring services, existing frontend interview UI.

---

## File structure and responsibilities

### Backend files to create
- `src/backend/app/services/orchestrator.py` — interview loop orchestration helpers
- `src/backend/app/services/transcript_quality.py` — post-STT transcript reliability scoring
- `src/backend/app/services/prosody_scoring.py` — lightweight speaking-signal scoring from text
- `src/backend/app/services/interview_context.py` — build interview context from CV + JD before session start
- `src/backend/app/services/turn_evaluator.py` — evaluate each answer for correctness, depth, and communication
- `src/backend/app/services/coaching_summary.py` — post-interview coaching synthesis helpers
- `src/backend/app/services/ai_metrics.py` — latency and usage metadata helpers

### Backend files to modify
- `src/backend/app/models.py` — request/response schemas for interview context, turn analysis, and coaching outputs
- `src/backend/app/routers/interview.py` — orchestrated interview turn loop with lightweight per-turn evaluation
- `src/backend/app/routers/cv.py` — optional pre-interview context extraction from CV + JD
- `src/backend/app/ai_service.py` — normalized provider/model metadata helpers
- `src/backend/app/routers/admin.py` — optional metrics endpoint

### Frontend files to create
- `src/frontend/components/Interview/SignalCards.tsx` — show transcript and speaking signals during interview
- `src/frontend/components/Interview/TurnFeedbackPanel.tsx` — show concise per-turn evaluation signals
- `src/frontend/components/Interview/CoachingSummaryPanel.tsx` — show post-interview strengths, gaps, and next steps
- `src/frontend/components/Modals/CV/CVInterviewContextPanel.tsx` — show lightweight CV/JD interview context summary only

### Frontend files to modify
- `src/frontend/hooks/useChat.ts` — manage turn analysis and interview context state
- `src/frontend/services/api.ts` — update interview and context response typing
- `src/frontend/app/interview/page.tsx` — render live interview signals and post-interview coaching summary
- `src/frontend/components/Modals/ReviewCVModal.tsx` — show context summary, not a heavy CV reasoning UI

### Tests to create
- `src/backend/tests/test_transcript_quality.py`
- `src/backend/tests/test_prosody_scoring.py`
- `src/backend/tests/test_interview_context.py`
- `src/backend/tests/test_turn_evaluator.py`
- `src/backend/tests/test_coaching_summary.py`
- `src/backend/tests/test_orchestrator.py`

Because the repo does not currently expose clear frontend app-level test files, frontend validation remains focused on lint plus manual verification of the interview loop.

---

### Task 1: Create orchestrator and structured interview response foundation
**Priority:** P2

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
        analysis={"turn_evaluation": {"correctness": "partial"}},
        usage={"provider": "gemini"},
        trace_id="trace-123",
    )

    assert result["content"] == "Next question?"
    assert result["analysis"]["turn_evaluation"]["correctness"] == "partial"
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

- [ ] **Step 4: Add minimal schema support in `models.py`**

```python
from pydantic import BaseModel, Field
from typing import Any


class InterviewAIResponse(BaseModel):
    content: str
    analysis: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)
    trace_id: str
```

- [ ] **Step 5: Add normalized provider metadata helper in `ai_service.py`**

```python
import time


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
git commit -m "feat: add interview orchestration foundation"
```

---

### Task 2: Add post-STT transcript reliability scoring
**Priority:** P2

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

- [ ] **Step 3: Write minimal transcript-quality implementation**

```python
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

- [ ] **Step 4: Score transcript quality in `interview.py` and add only a light prompt hint**

```python
from ..services.transcript_quality import score_transcript_quality

transcript_analysis = score_transcript_quality(request.user_text, request.lang or "vi")
if transcript_analysis["low_quality_flag"]:
    base_prompt += "\n\n[TRANSCRIPT QUALITY] The transcribed answer may be incomplete or unclear. Do not over-interpret missing details. Ask a short clarifying follow-up only if needed."
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest src/backend/tests/test_transcript_quality.py::test_score_transcript_quality_flags_short_low_quality_english_text -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/backend/app/services/transcript_quality.py src/backend/app/routers/interview.py src/backend/tests/test_transcript_quality.py
git commit -m "feat: add post-stt transcript reliability scoring"
```

---

### Task 3: Add lightweight text-based speaking signals
**Priority:** P2

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

- [ ] **Step 3: Write minimal speaking-signal implementation**

```python
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

- [ ] **Step 4: Add speaking signal hint in `interview.py`**

```python
from ..services.prosody_scoring import score_speaking_signals

speaking_signals = score_speaking_signals(request.user_text)
if speaking_signals["speaking_signal"] == "hesitant":
    base_prompt += "\n\n[SPEAKING SIGNAL] The user's answer appears hesitant or filler-heavy. Keep the response supportive and use a concise follow-up if clarification is useful."
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest src/backend/tests/test_prosody_scoring.py::test_score_speaking_signals_returns_expected_keys_from_text -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/backend/app/services/prosody_scoring.py src/backend/app/routers/interview.py src/backend/tests/test_prosody_scoring.py
git commit -m "feat: add lightweight speaking signal scoring"
```

---

### Task 4: Build pre-interview context from CV + JD
**Priority:** P1

**Files:**
- Create: `src/backend/app/services/interview_context.py`
- Modify: `src/backend/app/routers/cv.py`
- Modify: `src/backend/app/models.py`
- Test: `src/backend/tests/test_interview_context.py`

- [ ] **Step 1: Write the failing interview-context test**

```python
from app.services.interview_context import build_interview_context


def test_build_interview_context_reports_strengths_gaps_and_topics():
    result = build_interview_context(
        cv_skills=["FastAPI", "Python"],
        jd_skills=["Python", "FastAPI", "System Design"],
    )

    assert result["match_score"] < 1.0
    assert "System Design" in result["skill_gaps"]
    assert result["target_topics"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest src/backend/tests/test_interview_context.py::test_build_interview_context_reports_strengths_gaps_and_topics -v`
Expected: FAIL with import error or missing function error.

- [ ] **Step 3: Write minimal interview-context builder**

```python

def build_interview_context(cv_skills: list[str], jd_skills: list[str]) -> dict:
    cv_set = {skill.strip() for skill in cv_skills if skill.strip()}
    jd_set = {skill.strip() for skill in jd_skills if skill.strip()}
    matched = sorted(cv_set & jd_set)
    missing = sorted(jd_set - cv_set)
    target_topics = missing[:3] if missing else matched[:3]
    return {
        "match_score": round(len(matched) / max(len(jd_set), 1), 2),
        "highlighted_strengths": matched[:3],
        "skill_gaps": missing,
        "target_topics": target_topics,
    }
```

- [ ] **Step 4: Use CV + JD analysis to produce pre-interview context in `cv.py`**

```python
import re
from ..services.interview_context import build_interview_context


def extract_skill_candidates(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,\n]", text) if part.strip()]

cv_skills = extract_skill_candidates(cv_text)
jd_skills = extract_skill_candidates(jd_text)
interview_context = build_interview_context(cv_skills, jd_skills)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest src/backend/tests/test_interview_context.py::test_build_interview_context_reports_strengths_gaps_and_topics -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/backend/app/services/interview_context.py src/backend/app/routers/cv.py src/backend/app/models.py src/backend/tests/test_interview_context.py
git commit -m "feat: add pre interview context builder"
```

---

### Task 5: Add turn evaluator for correctness, depth, and communication
**Priority:** P1

**Files:**
- Create: `src/backend/app/services/turn_evaluator.py`
- Modify: `src/backend/app/routers/interview.py`
- Test: `src/backend/tests/test_turn_evaluator.py`

- [ ] **Step 1: Write the failing turn-evaluator test**

```python
from app.services.turn_evaluator import evaluate_turn


def test_evaluate_turn_returns_three_core_dimensions():
    result = evaluate_turn(
        answer_text="I used FastAPI to build APIs.",
        target_topic="FastAPI",
    )

    assert "correctness" in result
    assert "depth" in result
    assert "communication" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest src/backend/tests/test_turn_evaluator.py::test_evaluate_turn_returns_three_core_dimensions -v`
Expected: FAIL with import error or missing function error.

- [ ] **Step 3: Write minimal lightweight turn evaluator**

```python
import re


def evaluate_turn(answer_text: str, target_topic: str) -> dict:
    words = re.findall(r"[a-zA-ZÀ-ỹ']+", answer_text or "")
    normalized = (answer_text or "").lower()
    correctness = "partial" if target_topic.lower() in normalized else "weak"
    depth = "adequate" if len(words) >= 12 else "shallow"
    communication = "clear" if len(words) >= 6 else "brief"
    return {
        "correctness": correctness,
        "depth": depth,
        "communication": communication,
    }
```

- [ ] **Step 4: Merge turn evaluation into `interview.py` analysis block**

```python
from ..services.turn_evaluator import evaluate_turn

turn_evaluation = evaluate_turn(request.user_text, next_topic)
analysis = {
    "transcript": transcript_analysis,
    "speaking_signals": speaking_signals,
    "turn_evaluation": turn_evaluation,
}
```

- [ ] **Step 5: Add a light prompt hint from turn evaluation**

```python
if turn_evaluation["depth"] == "shallow":
    base_prompt += "\n\n[TURN EVALUATION] The user's answer appears shallow. Ask a concise follow-up that probes reasoning or examples."
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest src/backend/tests/test_turn_evaluator.py::test_evaluate_turn_returns_three_core_dimensions -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/backend/app/services/turn_evaluator.py src/backend/app/routers/interview.py src/backend/tests/test_turn_evaluator.py
git commit -m "feat: add interview turn evaluator"
```

---

### Task 6: Route interview turns through the low-latency loop
**Priority:** P1

**Files:**
- Modify: `src/backend/app/routers/interview.py`
- Modify: `src/backend/app/models.py`
- Test: `src/backend/tests/test_orchestrator.py`

- [ ] **Step 1: Write the failing structured turn-loop test**

```python
from app.services.orchestrator import build_interview_result


def test_interview_result_contains_turn_evaluation_and_signals():
    result = build_interview_result(
        ai_text="Tell me about your API design choices.",
        analysis={
            "transcript": {"transcript_confidence": 0.9, "low_quality_flag": False},
            "speaking_signals": {"clarity_score": 0.88, "speaking_signal": "clear"},
            "turn_evaluation": {"correctness": "partial", "depth": "adequate", "communication": "clear"},
        },
        usage={"provider": "gemini"},
        trace_id="trace-456",
    )

    assert result["analysis"]["turn_evaluation"]["depth"] == "adequate"
    assert result["analysis"]["speaking_signals"]["clarity_score"] == 0.88
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest src/backend/tests/test_orchestrator.py::test_interview_result_contains_turn_evaluation_and_signals -v`
Expected: FAIL until structured interview analysis is aligned.

- [ ] **Step 3: Extend `ChatRequest` to carry optional interview context**

```python
from typing import Any

interview_context: dict[str, Any] | None = None
audio_meta: dict[str, Any] | None = None
lang: str | None = None
```

- [ ] **Step 4: Use interview context to steer question planning and follow-up topic choice**

```python
interview_context = request.interview_context or {}
target_topics = interview_context.get("target_topics") or [request.jd_text]
next_topic = target_topics[0]
```

- [ ] **Step 5: Return structured low-latency interview result**

```python
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

- [ ] **Step 6: Run tests to verify the structured turn loop passes**

Run: `pytest src/backend/tests/test_orchestrator.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/backend/app/routers/interview.py src/backend/app/models.py src/backend/tests/test_orchestrator.py
git commit -m "feat: add low latency interview turn loop"
```

---

### Task 7: Add post-interview coaching synthesis
**Priority:** P2

**Files:**
- Create: `src/backend/app/services/coaching_summary.py`
- Modify: `src/backend/app/routers/interview.py`
- Test: `src/backend/tests/test_coaching_summary.py`

- [ ] **Step 1: Write the failing coaching-summary test**

```python
from app.services.coaching_summary import build_coaching_summary


def test_build_coaching_summary_returns_strengths_gaps_and_next_steps():
    result = build_coaching_summary(
        turn_evaluations=[
            {"correctness": "partial", "depth": "shallow", "communication": "clear"},
            {"correctness": "weak", "depth": "shallow", "communication": "brief"},
        ],
        interview_context={"target_topics": ["System Design", "FastAPI"]},
    )

    assert "strengths" in result
    assert "gaps" in result
    assert "next_steps" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest src/backend/tests/test_coaching_summary.py::test_build_coaching_summary_returns_strengths_gaps_and_next_steps -v`
Expected: FAIL with import error or missing function error.

- [ ] **Step 3: Write minimal coaching-summary implementation**

```python

def build_coaching_summary(turn_evaluations: list[dict], interview_context: dict) -> dict:
    weak_turns = [turn for turn in turn_evaluations if turn.get("correctness") == "weak"]
    shallow_turns = [turn for turn in turn_evaluations if turn.get("depth") == "shallow"]
    return {
        "strengths": ["clear communication"] if turn_evaluations else [],
        "gaps": ["technical depth"] if shallow_turns else [],
        "next_steps": interview_context.get("target_topics", [])[:3],
        "weak_turn_count": len(weak_turns),
    }
```

- [ ] **Step 4: Use coaching summary in post-interview report path**

```python
from ..services.coaching_summary import build_coaching_summary

coaching_summary = build_coaching_summary(turn_evaluations, interview_context)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest src/backend/tests/test_coaching_summary.py::test_build_coaching_summary_returns_strengths_gaps_and_next_steps -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/backend/app/services/coaching_summary.py src/backend/app/routers/interview.py src/backend/tests/test_coaching_summary.py
git commit -m "feat: add post interview coaching summary"
```

---

### Task 8: Show interview-first proof points in the frontend
**Priority:** P1

**Files:**
- Create: `src/frontend/components/Interview/SignalCards.tsx`
- Create: `src/frontend/components/Interview/TurnFeedbackPanel.tsx`
- Modify: `src/frontend/hooks/useChat.ts`
- Modify: `src/frontend/services/api.ts`
- Modify: `src/frontend/app/interview/page.tsx`

- [ ] **Step 1: Add frontend interview response typings**

```ts
export type InterviewAnalysis = {
  transcript?: {
    transcript_confidence: number;
    low_quality_flag: boolean;
    word_count?: number;
    quality_reason?: string;
  };
  speaking_signals?: {
    filler_rate: number;
    clarity_score: number;
    speaking_signal: string;
    pause_hint?: number | null;
  };
  turn_evaluation?: {
    correctness: string;
    depth: string;
    communication: string;
  };
};

export type InterviewAIResponse = {
  content: string;
  analysis: InterviewAnalysis;
  usage: Record<string, unknown>;
  trace_id: string;
};
```

- [ ] **Step 2: Update `useChat.ts` to store interview context and turn analysis**

```ts
const [analysis, setAnalysis] = useState<InterviewAnalysis | null>(null);

setAnalysis(response.analysis);
```

- [ ] **Step 3: Create signal cards component**

```tsx
export function SignalCards({ analysis }: { analysis: InterviewAnalysis | null }) {
  if (!analysis) return null;

  return (
    <div className="grid gap-3 md:grid-cols-3">
      <div>Transcript confidence: {analysis.transcript?.transcript_confidence ?? "-"}</div>
      <div>Clarity: {analysis.speaking_signals?.clarity_score ?? "-"}</div>
      <div>Speaking signal: {analysis.speaking_signals?.speaking_signal ?? "-"}</div>
    </div>
  );
}
```

- [ ] **Step 4: Create turn feedback panel**

```tsx
export function TurnFeedbackPanel({ analysis }: { analysis: InterviewAnalysis | null }) {
  if (!analysis?.turn_evaluation) return null;

  return (
    <div className="space-y-2 rounded border p-3">
      <div>Correctness: {analysis.turn_evaluation.correctness}</div>
      <div>Depth: {analysis.turn_evaluation.depth}</div>
      <div>Communication: {analysis.turn_evaluation.communication}</div>
    </div>
  );
}
```

- [ ] **Step 5: Render signal cards and turn feedback in `app/interview/page.tsx`**

```tsx
<SignalCards analysis={analysis} />
<TurnFeedbackPanel analysis={analysis} />
```

- [ ] **Step 6: Run frontend verification**

Run: `npm run lint`
Expected: PASS or only pre-existing unrelated warnings.

- [ ] **Step 7: Manual verification**

Verify:
- interview still works normally
- signal cards update per turn
- turn feedback panel appears without blocking the live flow

- [ ] **Step 8: Commit**

```bash
git add src/frontend/components/Interview/SignalCards.tsx src/frontend/components/Interview/TurnFeedbackPanel.tsx src/frontend/hooks/useChat.ts src/frontend/services/api.ts src/frontend/app/interview/page.tsx
git commit -m "feat: show interview first proof signals"
```

---

### Task 9: Use CV + JD analysis only as interview setup context in the frontend
**Priority:** P2

**Files:**
- Create: `src/frontend/components/Modals/CV/CVInterviewContextPanel.tsx`
- Modify: `src/frontend/components/Modals/ReviewCVModal.tsx`
- Modify: `src/frontend/services/api.ts`
- Modify: `src/frontend/app/interview/page.tsx`

- [ ] **Step 1: Add pre-interview context response typings**

```ts
export type InterviewContextResponse = {
  content: string;
  analysis: {
    interview_context?: {
      match_score: number;
      highlighted_strengths: string[];
      skill_gaps: string[];
      target_topics: string[];
    };
  };
  evidence: {
    highlighted_strengths?: string[];
    skill_gaps?: string[];
    target_topics?: string[];
  };
  usage: Record<string, unknown>;
  trace_id: string;
};
```

- [ ] **Step 2: Create lightweight CV/JD interview-context panel**

```tsx
export function CVInterviewContextPanel({ result }: { result: InterviewContextResponse | null }) {
  if (!result) return null;

  return (
    <div className="space-y-2 rounded border p-3">
      <div>Match score: {result.analysis.interview_context?.match_score ?? "-"}</div>
      <div>Strengths: {(result.evidence.highlighted_strengths || []).join(", ")}</div>
      <div>Target topics: {(result.evidence.target_topics || []).join(", ")}</div>
    </div>
  );
}
```

- [ ] **Step 3: Save interview context for the interview page**

```ts
sessionStorage.setItem(
  "interview_context",
  JSON.stringify(result?.analysis.interview_context ?? null)
);
```

- [ ] **Step 4: Read interview context before the interview starts and attach it to requests**

```ts
const rawInterviewContext = sessionStorage.getItem("interview_context");
const interviewContext = rawInterviewContext ? JSON.parse(rawInterviewContext) : null;

body: JSON.stringify({
  ...payload,
  interview_context: interviewContext,
})
```

- [ ] **Step 5: Run frontend verification**

Run: `npm run lint`
Expected: PASS or only pre-existing unrelated warnings.

- [ ] **Step 6: Manual verification**

Verify:
- CV/JD setup still works
- only lightweight setup summary is shown
- target topics influence the interview start

- [ ] **Step 7: Commit**

```bash
git add src/frontend/components/Modals/CV/CVInterviewContextPanel.tsx src/frontend/components/Modals/ReviewCVModal.tsx src/frontend/services/api.ts src/frontend/app/interview/page.tsx
git commit -m "feat: use cv jd as interview setup context"
```

---

### Task 10: Add post-interview coaching summary in the frontend and lightweight metrics
**Priority:** P2 for coaching summary, P3 for admin metrics

**Files:**
- Create: `src/frontend/components/Interview/CoachingSummaryPanel.tsx`
- Modify: `src/backend/app/routers/admin.py`
- Modify: `src/frontend/services/api.ts`
- Modify: `src/frontend/app/interview/page.tsx`

- [ ] **Step 1: Add coaching summary typing**

```ts
export type CoachingSummary = {
  strengths: string[];
  gaps: string[];
  next_steps: string[];
  weak_turn_count: number;
};
```

- [ ] **Step 2: Create minimal coaching summary panel**

```tsx
export function CoachingSummaryPanel({ summary }: { summary: CoachingSummary | null }) {
  if (!summary) return null;

  return (
    <div className="space-y-2 rounded border p-3">
      <div>Strengths: {summary.strengths.join(", ")}</div>
      <div>Gaps: {summary.gaps.join(", ")}</div>
      <div>Next steps: {summary.next_steps.join(", ")}</div>
    </div>
  );
}
```

- [ ] **Step 3: Add lightweight metrics endpoint in `admin.py`**

```python
@router.get("/api/admin/ai-interview-metrics")
def get_ai_interview_metrics():
    return {
        "proof_points": ["transcript_reliability", "turn_evaluation", "post_interview_coaching"],
        "fallback_enabled": True,
    }
```

- [ ] **Step 4: Render coaching summary after interview ends**

```tsx
<CoachingSummaryPanel summary={coachingSummary} />
```

- [ ] **Step 5: Run verification**

Run backend tests: `pytest src/backend/tests -v`
Run frontend lint: `npm run lint`
Expected: PASS or only pre-existing unrelated issues that are documented before merge.

- [ ] **Step 6: Manual verification**

Verify:
- coaching summary appears only after interview completion
- wording feels like interview coaching, not CV review
- live interview remains responsive during normal turns

- [ ] **Step 7: Commit**

```bash
git add src/frontend/components/Interview/CoachingSummaryPanel.tsx src/backend/app/routers/admin.py src/frontend/services/api.ts src/frontend/app/interview/page.tsx
git commit -m "feat: add post interview coaching summary"
```

---

## Self-review

### Spec coverage
- Interview-first product framing: covered by Tasks 1, 4, 5, 6, 8, 9, and 10
- Low-latency live loop: covered by Tasks 2, 3, 5, and 6
- CV/JD as context feeder only: covered by Task 4 and Task 9
- Post-interview coaching synthesis: covered by Tasks 7 and 10
- Explainability and visible proof points: covered by Tasks 8, 9, and 10

### Placeholder scan
- No TBD/TODO placeholders remain
- Each code-writing step includes concrete code blocks
- Each verification step includes concrete commands and expected outcomes

### Type consistency
- Interview signal keys are `transcript`, `speaking_signals`, and `turn_evaluation`
- Pre-interview context keys are `match_score`, `highlighted_strengths`, `skill_gaps`, and `target_topics`
- Post-interview coaching keys are `strengths`, `gaps`, `next_steps`, and `weak_turn_count`

---
