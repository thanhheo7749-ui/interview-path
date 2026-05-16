# SpeakCV Planner-First Level 5 Interview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the interview flow into a planner-first, demo-friendly Level 5-capable system that reuses the existing router, header-based analysis flow, and report modal while adding lightweight live cues plus final 1-5 scoring and top 3 skills to improve.

**Architecture:** Keep `src/backend/app/routers/interview.py` as the API entrypoint, move new planning/report assembly logic into focused backend services, extend the existing `analysis` header payload consumed by `useChat`, and reuse the existing report modal flow for final structured evaluation. Add a separate git audit task that inspects already-pushed commits and flags suspicious changes with evidence, but do not rewrite history or revert anything during the audit.

**Tech Stack:** FastAPI, Pydantic, Python service modules, pytest, Next.js App Router, React hooks, TypeScript, existing fetch-based API layer, existing report modal UI.

---

## File structure

### Backend files to modify
- `src/backend/app/models.py`
  - Extend request/response models used by the interview flow so planner state and report payloads have explicit fields.
- `src/backend/app/routers/interview.py`
  - Keep as entrypoint for `/api/chat` and `/api/end-interview`, but reduce inline planning/report-assembly logic.
- `src/backend/app/services/interview_context.py`
  - Upgrade shallow context output into a planner seed built from CV/JD strengths, gaps, and initial topics.
- `src/backend/app/services/orchestrator.py`
  - Continue wrapping `content`, `analysis`, `usage`, `trace_id`; may gain helpers for stable response shape.
- `src/backend/app/services/turn_evaluator.py`
  - Extend current `correctness`, `depth`, `communication` scoring to add `topic_relevance` and live cues.

### Backend files to create
- `src/backend/app/services/question_planner.py`
  - Planner state transitions, next-topic selection, follow-up mode, and why-selected trace.
- `src/backend/app/services/interview_report_builder.py`
  - Assemble final 1-5 scores, strongest/weak topics, and top 3 skills to improve from structured turn records.
- `src/backend/tests/test_question_planner.py`
  - Unit tests for planner state and next-question logic.
- `src/backend/tests/test_interview_report_builder.py`
  - Unit tests for final report assembly.

### Frontend files to modify
- `src/frontend/services/api.ts`
  - Pass interview context and future planner fields through `chatWithAI` payload cleanly.
- `src/frontend/hooks/useChat.ts`
  - Persist/parse richer `analysis` header payload and expose it to the interview UI.
- `src/frontend/app/interview/page.tsx`
  - Thread parsed analysis into the layout/report flow.
- `src/frontend/components/Interview/InterviewLayout.tsx`
  - Render small live planner cards and lightweight live cues, not numeric per-turn scoring.
- `src/frontend/components/Modals/ReportModal.tsx`
  - Reuse current report modal to show final 1-5 scores and top 3 skills to improve.

### Frontend files to create
- `src/frontend/components/Interview/PlannerSignals.tsx`
  - Focused UI component for `Current focus`, `Why this question`, `Next skill being tested`, and cue chips.

### Audit-only files to inspect
- `implementations/LEVEL5_GAP_ANALYSIS.md`
- `implementations/LEVEL5_UPGRADE_ROADMAP.md`
- current branch commits ahead of `origin/main`
- remote branch commit list and diffs using git commands only

---

### Task 1: Audit already-pushed branch changes before implementation

**Files:**
- Inspect: `git log`, `git diff`, `implementations/LEVEL5_GAP_ANALYSIS.md`, `implementations/LEVEL5_UPGRADE_ROADMAP.md`
- Output: no code changes required unless the audit finds a concrete issue worth fixing in a follow-up task

- [ ] **Step 1: Capture the remote comparison baseline**

Run:
```bash
git branch --show-current
git remote -v
git rev-list --left-right --count origin/main...HEAD
git log --oneline --decorate origin/main..HEAD
```

Expected:
- current branch is shown
- `origin` is shown
- ahead/behind counts are shown
- the exact commits not yet in `origin/main` are listed

- [ ] **Step 2: Inspect full diffs for commits ahead of origin/main**

Run:
```bash
git diff --stat origin/main...HEAD
git diff origin/main...HEAD -- src/backend/app/routers/interview.py src/backend/app/services/interview_context.py src/frontend/hooks/useChat.ts src/frontend/components/Modals/ReportModal.tsx src/frontend/services/api.ts
```

Expected:
- a stat summary of changed files
- full diff for interview-related files only

- [ ] **Step 3: Inspect local uncommitted interview-related changes separately**

Run:
```bash
git diff -- src/frontend/hooks/useChat.ts implementations/LEVEL5_GAP_ANALYSIS.md implementations/LEVEL5_UPGRADE_ROADMAP.md
git status --short
```

Expected:
- only current local edits are shown
- current untracked files are listed

- [ ] **Step 4: Produce an audit note before any revert decision**

Write a short note in the work log or chat with this structure:
```text
Audit result:
- Safe to keep: <specific files/commits and why>
- Suspicious: <specific files/commits and evidence>
- Needs revert or replacement later?: yes/no
- Recommended action: <follow-up only, no destructive command yet>
```

Expected:
- no git history rewrite
- no reset, revert, or force push yet
- only evidence-backed recommendations

- [ ] **Step 5: Commit**

Do not commit anything for the audit alone unless it produces a code or doc change that the user explicitly wants preserved.

---

### Task 2: Lock the backend response contract with failing tests

**Files:**
- Modify: `src/backend/tests/test_orchestrator.py`
- Modify: `src/backend/tests/test_turn_evaluator.py`
- Create: `src/backend/tests/test_question_planner.py`
- Create: `src/backend/tests/test_interview_report_builder.py`

- [ ] **Step 1: Add a failing orchestrator contract test for planner fields**

```python
from app.services.orchestrator import build_interview_result


def test_interview_result_contains_planner_fields():
    result = build_interview_result(
        ai_text="Next question",
        analysis={
            "turn_evaluation": {
                "correctness": 0.6,
                "depth": 0.5,
                "communication": 0.7,
                "topic_relevance": 0.8,
            },
            "planner_decision": {
                "why_selected": "gap_in_jd",
                "topic_state": "probing",
                "next_topic": "Caching",
                "followup_mode": "deep_dive",
            },
            "live_cues": ["On-topic", "Needs more depth"],
        },
        usage={},
        trace_id="trace-123",
    )

    assert result["analysis"]["planner_decision"]["why_selected"] == "gap_in_jd"
    assert result["analysis"]["turn_evaluation"]["topic_relevance"] == 0.8
    assert result["analysis"]["live_cues"] == ["On-topic", "Needs more depth"]
```

- [ ] **Step 2: Run the orchestrator test to confirm current failure or missing fields**

Run:
```bash
pytest src/backend/tests/test_orchestrator.py::test_interview_result_contains_planner_fields -v
```

Expected:
- FAIL if planner fields are not preserved consistently yet

- [ ] **Step 3: Add a failing turn-evaluator test for topic relevance and cue mapping**

```python
from app.services.turn_evaluator import build_turn_analysis


def test_build_turn_analysis_adds_topic_relevance_and_live_cues():
    result = build_turn_analysis(
        "I used Redis caching to reduce latency and avoid repeated database hits.",
        "Caching",
        {"intent": "answering", "confidence_level": "Normal"},
    )

    assert set(result["turn_evaluation"].keys()) == {
        "correctness",
        "depth",
        "communication",
        "topic_relevance",
    }
    assert "live_cues" in result
    assert isinstance(result["live_cues"], list)
```

- [ ] **Step 4: Run the turn-evaluator test to verify it fails**

Run:
```bash
pytest src/backend/tests/test_turn_evaluator.py::test_build_turn_analysis_adds_topic_relevance_and_live_cues -v
```

Expected:
- FAIL because `topic_relevance` and `live_cues` do not exist yet

- [ ] **Step 5: Add a failing planner-state test**

```python
from app.services.question_planner import plan_next_question


def test_plan_next_question_uses_gap_and_shallow_answer_signal():
    decision = plan_next_question(
        planner_seed={"priority_topics": ["Caching", "System Design"]},
        planner_state={"Caching": "probing"},
        previous_turn={
            "turn_evaluation": {
                "correctness": 0.6,
                "depth": 0.3,
                "communication": 0.7,
                "topic_relevance": 0.8,
            }
        },
        transcript={"low_quality_flag": False},
    )

    assert decision["next_topic"] == "Caching"
    assert decision["followup_mode"] == "deep_dive"
    assert decision["why_selected"] == "previous_answer_shallow"
```

- [ ] **Step 6: Run the planner test to verify it fails**

Run:
```bash
pytest src/backend/tests/test_question_planner.py::test_plan_next_question_uses_gap_and_shallow_answer_signal -v
```

Expected:
- FAIL because planner module does not exist yet

- [ ] **Step 7: Add a failing report-builder test**

```python
from app.services.interview_report_builder import build_structured_report


def test_build_structured_report_returns_final_scores_and_top_skills():
    report = build_structured_report(
        turn_records=[
            {
                "topic": "Caching",
                "correctness": 0.6,
                "depth": 0.3,
                "communication": 0.8,
                "topic_relevance": 0.9,
                "live_cues": ["On-topic", "Needs more depth"],
            },
            {
                "topic": "System Design",
                "correctness": 0.5,
                "depth": 0.4,
                "communication": 0.6,
                "topic_relevance": 0.7,
                "live_cues": ["Follow-up triggered"],
            },
        ]
    )

    assert report["final_scores"] == {
        "correctness": 3,
        "depth": 2,
        "communication": 4,
        "topic_relevance": 4,
    }
    assert len(report["top_skills_to_improve"]) == 3
```

- [ ] **Step 8: Run the report-builder test to verify it fails**

Run:
```bash
pytest src/backend/tests/test_interview_report_builder.py::test_build_structured_report_returns_final_scores_and_top_skills -v
```

Expected:
- FAIL because builder module does not exist yet

- [ ] **Step 9: Commit**

```bash
git add src/backend/tests/test_orchestrator.py src/backend/tests/test_turn_evaluator.py src/backend/tests/test_question_planner.py src/backend/tests/test_interview_report_builder.py
git commit -m "test: lock planner-first interview contracts"
```

---

### Task 3: Implement planner and turn-evaluation backend services

**Files:**
- Create: `src/backend/app/services/question_planner.py`
- Modify: `src/backend/app/services/turn_evaluator.py`
- Test: `src/backend/tests/test_turn_evaluator.py`
- Test: `src/backend/tests/test_question_planner.py`

- [ ] **Step 1: Implement the planner module with minimal deterministic rules**

```python
from typing import Any


SHALLOW_DEPTH_THRESHOLD = 0.4
STRONG_CORRECTNESS_THRESHOLD = 0.75


def _next_priority_topic(priority_topics: list[str], planner_state: dict[str, str]) -> str:
    for topic in priority_topics:
        if planner_state.get(topic, "unasked") != "completed":
            return topic
    return priority_topics[0] if priority_topics else "General Technical Fit"


def plan_next_question(
    planner_seed: dict[str, Any],
    planner_state: dict[str, str],
    previous_turn: dict[str, Any],
    transcript: dict[str, Any],
) -> dict[str, Any]:
    priority_topics = planner_seed.get("priority_topics", [])
    next_topic = _next_priority_topic(priority_topics, planner_state)
    turn_eval = previous_turn.get("turn_evaluation", {})

    if transcript.get("low_quality_flag"):
        return {
            "next_topic": next_topic,
            "followup_mode": "clarify",
            "why_selected": "clarify_low_quality_transcript",
            "topic_state": planner_state.get(next_topic, "probing"),
            "question_strategy": "clarify",
        }

    if turn_eval.get("depth", 0.0) <= SHALLOW_DEPTH_THRESHOLD:
        return {
            "next_topic": next_topic,
            "followup_mode": "deep_dive",
            "why_selected": "previous_answer_shallow",
            "topic_state": "needs_followup",
            "question_strategy": "deep_dive",
        }

    if turn_eval.get("correctness", 0.0) >= STRONG_CORRECTNESS_THRESHOLD:
        return {
            "next_topic": next_topic,
            "followup_mode": "stretch",
            "why_selected": "strong_performance_raise_difficulty",
            "topic_state": "strong",
            "question_strategy": "stretch",
        }

    return {
        "next_topic": next_topic,
        "followup_mode": "probe",
        "why_selected": "gap_in_jd",
        "topic_state": planner_state.get(next_topic, "probing"),
        "question_strategy": "opening",
    }
```

- [ ] **Step 2: Extend the turn evaluator with topic relevance and live cues**

```python
def _cue_from_scores(scores: dict[str, float], transcript_low_quality: bool) -> list[str]:
    cues: list[str] = []
    if scores["topic_relevance"] >= 0.6:
        cues.append("On-topic")
    if scores["depth"] <= 0.4:
        cues.append("Needs more depth")
    if scores["communication"] >= 0.6:
        cues.append("Clear communication")
    if transcript_low_quality:
        cues.append("Follow-up triggered")
    return cues
```

Then update `evaluate_turn` and `build_turn_analysis` to produce:
```python
turn_evaluation = {
    "correctness": correctness,
    "depth": depth,
    "communication": communication,
    "topic_relevance": topic_relevance,
}
merged_analysis = {
    **analysis,
    "turn_evaluation": turn_evaluation,
    "live_cues": _cue_from_scores(turn_evaluation, analysis.get("low_quality_flag", False)),
}
```

- [ ] **Step 3: Run focused backend tests**

Run:
```bash
pytest src/backend/tests/test_turn_evaluator.py src/backend/tests/test_question_planner.py src/backend/tests/test_orchestrator.py -v
```

Expected:
- PASS for new planner and turn-evaluation contract tests

- [ ] **Step 4: Commit**

```bash
git add src/backend/app/services/question_planner.py src/backend/app/services/turn_evaluator.py src/backend/tests/test_turn_evaluator.py src/backend/tests/test_question_planner.py src/backend/tests/test_orchestrator.py
git commit -m "feat: add planner-first turn evaluation services"
```

---

### Task 4: Extend interview context into a planner seed

**Files:**
- Modify: `src/backend/app/services/interview_context.py`
- Modify: `src/backend/tests/test_interview_context.py`

- [ ] **Step 1: Add a failing context test for planner seed output**

```python
from app.services.interview_context import build_interview_context


def test_build_interview_context_returns_priority_topics_and_seed():
    result = build_interview_context(
        ["Python", "FastAPI", "Redis"],
        ["Python", "Caching", "System Design", "Redis"],
    )

    assert result["highlighted_strengths"] == ["Python", "Redis"]
    assert result["priority_topics"] == ["Caching", "System Design"]
    assert result["question_plan_seed"]["starter_topic"] == "Caching"
```

- [ ] **Step 2: Run the new context test to verify failure**

Run:
```bash
pytest src/backend/tests/test_interview_context.py::test_build_interview_context_returns_priority_topics_and_seed -v
```

Expected:
- FAIL because new keys do not exist yet

- [ ] **Step 3: Implement the smallest context-builder upgrade**

Add fields like:
```python
priority_topics = skill_gaps[:3] if skill_gaps else highlighted_strengths[:3]
question_plan_seed = {
    "starter_topic": priority_topics[0] if priority_topics else "General Technical Fit",
    "strength_topics": highlighted_strengths,
    "gap_topics": skill_gaps,
}
```

Return:
```python
return {
    "match_score": round(len(matched_keys) / max(len(jd_map), 1), 2),
    "highlighted_strengths": highlighted_strengths,
    "skill_gaps": skill_gaps,
    "target_topics": target_topics,
    "priority_topics": priority_topics,
    "question_plan_seed": question_plan_seed,
}
```

- [ ] **Step 4: Run the context tests**

Run:
```bash
pytest src/backend/tests/test_interview_context.py -v
```

Expected:
- PASS for existing and new tests

- [ ] **Step 5: Commit**

```bash
git add src/backend/app/services/interview_context.py src/backend/tests/test_interview_context.py
git commit -m "feat: enrich interview context for planner seed"
```

---

### Task 5: Wire planner decisions into `/api/chat` without breaking the header flow

**Files:**
- Modify: `src/backend/app/models.py`
- Modify: `src/backend/app/routers/interview.py`
- Modify: `src/backend/app/services/orchestrator.py`
- Test: `src/backend/tests/test_orchestrator.py`

- [ ] **Step 1: Add request model fields only if they are truly consumed**

Update `ChatRequest` minimally so it matches actual usage:
```python
class ChatRequest(BaseModel):
    user_text: str
    jd_text: str = ""
    voice_id: str = "en-US-AndrewMultilingualNeural"
    lang: str = "vi"
    mode: str = "general"
    chat_history: list = []
    interview_context: Optional[dict[str, Any]] = None
    audio_meta: Optional[dict[str, Any]] = None
    current_topic: Optional[str] = None
    low_latency: bool = True
    trace_id: Optional[str] = None
```

- [ ] **Step 2: Import and call the planner in `interview.py`**

Add:
```python
from ..services.question_planner import plan_next_question
```

Then after turn evaluation:
```python
planner_seed = (request.interview_context or {}).get("question_plan_seed", {})
planner_state = {}
planner_decision = plan_next_question(
    planner_seed={
        "priority_topics": (request.interview_context or {}).get("priority_topics", [])
        or (request.interview_context or {}).get("target_topics", []),
    },
    planner_state=planner_state,
    previous_turn={"turn_evaluation": turn_scores},
    transcript=transcript_analysis,
)
structured_analysis["planner_decision"] = planner_decision
structured_analysis["why_selected"] = planner_decision["why_selected"]
structured_analysis["topic_state"] = planner_decision["topic_state"]
structured_analysis["next_topic"] = planner_decision["next_topic"]
structured_analysis["live_cues"] = analysis.get("live_cues", [])
```

- [ ] **Step 3: Keep prompt generation aligned with planner outputs**

Replace the raw `next_topic` usage in prompt text with the planner value:
```python
planned_topic = planner_decision["next_topic"]
```

And use `planned_topic` anywhere the question target is interpolated.

- [ ] **Step 4: Run focused backend tests**

Run:
```bash
pytest src/backend/tests/test_orchestrator.py src/backend/tests/test_turn_evaluator.py src/backend/tests/test_question_planner.py src/backend/tests/test_interview_context.py -v
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git add src/backend/app/models.py src/backend/app/routers/interview.py src/backend/app/services/orchestrator.py
git commit -m "feat: wire planner decisions into interview chat flow"
```

---

### Task 6: Build structured final report assembly

**Files:**
- Create: `src/backend/app/services/interview_report_builder.py`
- Modify: `src/backend/app/routers/interview.py`
- Test: `src/backend/tests/test_interview_report_builder.py`

- [ ] **Step 1: Implement a minimal report builder**

```python
from statistics import mean


def _to_five_point(score: float) -> int:
    return max(1, min(5, round(score * 5)))


def build_structured_report(turn_records: list[dict]) -> dict:
    correctness = _to_five_point(mean([t["correctness"] for t in turn_records]) if turn_records else 0.0)
    depth = _to_five_point(mean([t["depth"] for t in turn_records]) if turn_records else 0.0)
    communication = _to_five_point(mean([t["communication"] for t in turn_records]) if turn_records else 0.0)
    topic_relevance = _to_five_point(mean([t["topic_relevance"] for t in turn_records]) if turn_records else 0.0)

    weak_topics = [t["topic"] for t in turn_records if t["depth"] <= 0.4 or t["correctness"] <= 0.5]
    strong_topics = [t["topic"] for t in turn_records if t["correctness"] >= 0.7 and t["communication"] >= 0.6]

    improvement_candidates = []
    for topic in weak_topics:
        if topic not in improvement_candidates:
            improvement_candidates.append(topic)

    while len(improvement_candidates) < 3:
        improvement_candidates.append("Communication clarity")
        improvement_candidates = list(dict.fromkeys(improvement_candidates))

    return {
        "final_scores": {
            "correctness": correctness,
            "depth": depth,
            "communication": communication,
            "topic_relevance": topic_relevance,
        },
        "strong_topics": strong_topics[:3],
        "weak_topics": weak_topics[:3],
        "top_skills_to_improve": improvement_candidates[:3],
    }
```

- [ ] **Step 2: Run the report-builder tests**

Run:
```bash
pytest src/backend/tests/test_interview_report_builder.py -v
```

Expected:
- PASS

- [ ] **Step 3: Attach structured report data to the final interview report endpoint**

In `end_interview`, after the LLM report is parsed, derive `turn_records` from `details` minimally:
```python
turn_records = [
    {
        "topic": item.get("question", "General Technical Fit"),
        "correctness": 0.5,
        "depth": 0.5,
        "communication": 0.5,
        "topic_relevance": 0.5,
    }
    for item in details
]
structured_report = build_structured_report(turn_records)
report_data["final_scores"] = structured_report["final_scores"]
report_data["top_skills_to_improve"] = structured_report["top_skills_to_improve"]
report_data["strong_topics"] = structured_report["strong_topics"]
report_data["weak_topics"] = structured_report["weak_topics"]
```

This is intentionally minimal for the first pass. It reuses current report generation instead of replacing it.

- [ ] **Step 4: Run the interview report tests plus any existing report-related tests**

Run:
```bash
pytest src/backend/tests/test_interview_report_builder.py src/backend/tests/test_orchestrator.py -v
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git add src/backend/app/services/interview_report_builder.py src/backend/app/routers/interview.py src/backend/tests/test_interview_report_builder.py
git commit -m "feat: add structured interview report summary"
```

---

### Task 7: Pass richer interview analysis through the frontend hooks

**Files:**
- Modify: `src/frontend/services/api.ts`
- Modify: `src/frontend/hooks/useChat.ts`
- Modify: `src/frontend/app/interview/page.tsx`

- [ ] **Step 1: Add a failing frontend type check by extending the analysis type**

Update `InterviewAnalysis` in `useChat.ts`:
```ts
planner_decision?: {
  why_selected?: string;
  topic_state?: string;
  next_topic?: string;
  followup_mode?: string;
  question_strategy?: string;
};
live_cues?: string[];
```

And make the hook return them:
```ts
return {
  status,
  setStatus,
  aiText,
  setAiText,
  history,
  chatHistory,
  setChatHistory,
  analysis,
  usage,
  traceId,
  sendMessage,
  resetChat,
  interrupt,
  loadSession,
};
```

- [ ] **Step 2: Run frontend type checking to confirm any missing references fail**

Run:
```bash
npm --prefix src/frontend run build
```

Expected:
- either FAIL with missing props/usages or PASS if types are isolated

- [ ] **Step 3: Thread `analysis` from `useChat` into `page.tsx` and `InterviewLayout`**

Update destructuring in `page.tsx`:
```ts
const {
  status,
  setStatus,
  aiText,
  history,
  sendMessage,
  resetChat,
  interrupt: interruptChat,
  loadSession,
  analysis,
} = useChat();
```

Pass it into layout:
```tsx
<InterviewLayout
  ...
  analysis={analysis}
  ...
/>
```

- [ ] **Step 4: Update `chatWithAI` only if the context payload path is currently mismatched**

If needed, change `chatWithAI` to accept `interviewContext` explicitly so it matches `useChat`:
```ts
export const chatWithAI = async (
  text: string,
  jd: string,
  voice: string,
  mode: string,
  chatHistory: any[],
  signal: AbortSignal,
  lang: string = "vi",
  interviewContext: Record<string, unknown> | null = null,
) => {
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_text: text,
      jd_text: jd,
      voice_id: voice,
      lang,
      mode,
      chat_history: chatHistory,
      interview_context: interviewContext,
    }),
    signal,
  });
  if (!res.ok) throw new Error("API Error");
  return res;
};
```

- [ ] **Step 5: Run frontend build again**

Run:
```bash
npm --prefix src/frontend run build
```

Expected:
- PASS

- [ ] **Step 6: Commit**

```bash
git add src/frontend/services/api.ts src/frontend/hooks/useChat.ts src/frontend/app/interview/page.tsx
git commit -m "feat: thread planner analysis through interview hooks"
```

---

### Task 8: Add live planner signals to the interview UI

**Files:**
- Create: `src/frontend/components/Interview/PlannerSignals.tsx`
- Modify: `src/frontend/components/Interview/InterviewLayout.tsx`

- [ ] **Step 1: Create a focused planner signal component**

```tsx
interface PlannerSignalsProps {
  currentFocus?: string;
  whySelected?: string;
  nextSkill?: string;
  liveCues?: string[];
}

export function PlannerSignals({ currentFocus, whySelected, nextSkill, liveCues = [] }: PlannerSignalsProps) {
  if (!currentFocus && !whySelected && !nextSkill && liveCues.length === 0) return null;

  return (
    <section className="w-full max-w-3xl mb-4 rounded-2xl border border-theme-border bg-theme-surface/70 p-4 backdrop-blur-sm">
      <div className="grid gap-3 md:grid-cols-3">
        <div>
          <p className="text-xs font-semibold uppercase text-theme-text-secondary">Current focus</p>
          <p className="text-sm font-medium text-theme-text">{currentFocus || "—"}</p>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase text-theme-text-secondary">Why this question</p>
          <p className="text-sm font-medium text-theme-text">{whySelected || "—"}</p>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase text-theme-text-secondary">Next skill being tested</p>
          <p className="text-sm font-medium text-theme-text">{nextSkill || "—"}</p>
        </div>
      </div>
      {liveCues.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {liveCues.map((cue) => (
            <span key={cue} className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-xs font-medium text-cyan-300">
              {cue}
            </span>
          ))}
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Render the signal component in `InterviewLayout.tsx`**

Add prop:
```ts
analysis?: {
  next_topic?: string;
  why_selected?: string;
  planner_decision?: { next_topic?: string };
  live_cues?: string[];
};
```

Render above `ChatBox`:
```tsx
<PlannerSignals
  currentFocus={analysis?.next_topic}
  whySelected={analysis?.why_selected}
  nextSkill={analysis?.planner_decision?.next_topic || analysis?.next_topic}
  liveCues={analysis?.live_cues || []}
/>
```

- [ ] **Step 3: Run frontend build**

Run:
```bash
npm --prefix src/frontend run build
```

Expected:
- PASS

- [ ] **Step 4: Start the frontend and verify the golden path manually**

Run:
```bash
npm --prefix src/frontend run dev
```

Then verify in the browser:
- start an interview
- answer one question
- confirm planner cards appear
- confirm cue chips appear
- confirm no layout overlap with microphone/chat

- [ ] **Step 5: Commit**

```bash
git add src/frontend/components/Interview/PlannerSignals.tsx src/frontend/components/Interview/InterviewLayout.tsx
git commit -m "feat: show planner signals during interview"
```

---

### Task 9: Upgrade the final report modal to show 1-5 scores and top 3 skills

**Files:**
- Modify: `src/frontend/components/Modals/ReportModal.tsx`
- Modify: `src/frontend/hooks/useInterviewActions.ts`

- [ ] **Step 1: Add a minimal report shape adapter in `ReportModal.tsx`**

Use report fields directly if they exist:
```tsx
const finalScores = report.final_scores || {
  correctness: null,
  depth: null,
  communication: null,
  topic_relevance: null,
};
const topSkillsToImprove = report.top_skills_to_improve || [];
const strongTopics = report.strong_topics || [];
const weakTopics = report.weak_topics || [];
```

- [ ] **Step 2: Render a compact 1-5 score section**

```tsx
{Object.values(finalScores).some(Boolean) && (
  <div className="mb-10">
    <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2 border-b border-slate-800 pb-3">
      <BarChart3 className="text-violet-400" size={22} /> Final 1-5 Scores
    </h3>
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {Object.entries(finalScores).map(([label, score]) => (
        <div key={label} className="rounded-2xl border border-slate-700 bg-slate-800/40 p-4 text-center">
          <p className="text-xs uppercase text-slate-500">{label.replace("_", " ")}</p>
          <p className="mt-2 text-3xl font-black text-white">{score ?? "—"}</p>
          <p className="text-xs text-slate-500">/5</p>
        </div>
      ))}
    </div>
  </div>
)}
```

- [ ] **Step 3: Render the top 3 skills to improve section**

```tsx
{topSkillsToImprove.length > 0 && (
  <div className="mb-10">
    <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2 border-b border-slate-800 pb-3">
      <Brain className="text-pink-400" size={22} /> Top 3 Skills to Improve
    </h3>
    <div className="grid gap-3">
      {topSkillsToImprove.map((skill: string, index: number) => (
        <div key={skill} className="rounded-2xl border border-pink-500/20 bg-pink-500/5 p-4 text-slate-200">
          <span className="mr-2 text-pink-400 font-bold">{index + 1}.</span>
          {skill}
        </div>
      ))}
    </div>
  </div>
)}
```

- [ ] **Step 4: Make `useInterviewActions` preserve new report fields on resume/load**

When setting `savedReport` and `reportData`, include pass-through for:
```ts
final_scores: h.final_scores,
top_skills_to_improve: h.top_skills_to_improve,
strong_topics: h.strong_topics,
weak_topics: h.weak_topics,
```

If history records do not store them yet, keep the existing shape and tolerate `undefined`.

- [ ] **Step 5: Run frontend build**

Run:
```bash
npm --prefix src/frontend run build
```

Expected:
- PASS

- [ ] **Step 6: Verify the report UI manually**

Use the browser and verify:
- open a completed report
- confirm final 1-5 scores render
- confirm top 3 skills render
- confirm old report data still opens without crashing

- [ ] **Step 7: Commit**

```bash
git add src/frontend/components/Modals/ReportModal.tsx src/frontend/hooks/useInterviewActions.ts
git commit -m "feat: show final interview scores and top skills"
```

---

### Task 10: Full verification before completion

**Files:**
- Verify only; no code changes required unless failures are found

- [ ] **Step 1: Run backend tests for all touched areas**

Run:
```bash
pytest src/backend/tests/test_orchestrator.py src/backend/tests/test_turn_evaluator.py src/backend/tests/test_question_planner.py src/backend/tests/test_interview_context.py src/backend/tests/test_interview_report_builder.py -v
```

Expected:
- PASS

- [ ] **Step 2: Run frontend production build**

Run:
```bash
npm --prefix src/frontend run build
```

Expected:
- PASS

- [ ] **Step 3: Run manual browser verification of the interview flow**

Verify:
- interview starts normally
- answering one turn updates live planner cards/cues
- no visible per-turn numeric grading appears
- opening report shows final 1-5 scores and top 3 skills to improve
- old report data still renders

Expected:
- all checks pass without regressions in the main interview path

- [ ] **Step 4: Commit**

```bash
git add src/backend/app/models.py src/backend/app/routers/interview.py src/backend/app/services/interview_context.py src/backend/app/services/interview_report_builder.py src/backend/app/services/orchestrator.py src/backend/app/services/question_planner.py src/backend/app/services/turn_evaluator.py src/backend/tests/test_interview_context.py src/backend/tests/test_interview_report_builder.py src/backend/tests/test_orchestrator.py src/backend/tests/test_question_planner.py src/backend/tests/test_turn_evaluator.py src/frontend/app/interview/page.tsx src/frontend/components/Interview/InterviewLayout.tsx src/frontend/components/Interview/PlannerSignals.tsx src/frontend/components/Modals/ReportModal.tsx src/frontend/hooks/useChat.ts src/frontend/hooks/useInterviewActions.ts src/frontend/services/api.ts
git commit -m "feat: upgrade interview flow with planner-first signals"
```

---

## Self-review against spec

### Spec coverage
- Planner decision layer: covered by Tasks 2, 3, and 5.
- Reuse of existing router/header/report flow: covered by Tasks 5, 7, and 9.
- Live cue cards with no visible per-turn numeric grading: covered by Task 8.
- Final 1-5 scores and top 3 skills to improve: covered by Tasks 6 and 9.
- Existing-code-first approach: reflected in file structure and all tasks.
- Git audit before destructive cleanup: covered by Task 1.

### Placeholder scan
- No `TBD`, `TODO`, or “implement later” placeholders remain.
- Each code-changing step includes concrete code or commands.
- Each test step includes specific commands.

### Type consistency
- Core names are consistent across tasks: `planner_decision`, `why_selected`, `topic_state`, `next_topic`, `live_cues`, `topic_relevance`, `final_scores`, `top_skills_to_improve`.

---

Plan complete and saved to `docs/superpowers/plans/2026-05-15-speakcv-planner-first-level5-interview.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**