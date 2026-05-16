# SpeakCV Planner-First Level 5 Interview Design

## 1. Goal
SpeakCV should move toward a **planner-first, balanced Level 5 interview system** built on top of the current interview architecture.

The main proof point is not emotion detection or deep audio intelligence. The main proof point is that the system can **choose the next question for a visible reason**, show **lightweight in-session answer cues**, and produce a **clear post-session learning path** by combining:
- CV/JD context before the session
- answer quality during the session
- lightweight structured signals on each turn
- final structured scoring after the session

This direction keeps the product balanced:
- strong enough to look credible in a demo
- practical enough to improve real interview coaching
- lightweight enough to preserve live interview latency
- realistic for the current codebase, which already centers the flow in the interview router, services, and frontend hooks

---

## 2. Product positioning
SpeakCV should be presented as:

> An AI Interview Prep Coach with a planner-driven interview loop that uses CV/JD grounding and live answer quality to choose the next question explainably.

This is stronger than framing the product as:
- a generic AI interviewer
- a speech-emotion analyzer the current stack cannot defend
- a broad assistant where interview logic is only one feature among many

The key differentiator is:
- the system does not ask random questions
- the system does not rely on LLM prose alone
- the system can explain why each next question was selected

---

## 3. What Level 5 means for this design
For this version, Level 5 does not mean building a large multi-agent platform or a heavy multimodal stack.

SpeakCV can credibly move toward a Level 5-capable interview flow if it proves these four properties:
1. **Question planning is its own decision layer**
2. **The planner uses both grounded context and live performance**
3. **Each turn produces structured evaluation signals, not only text**
4. **The system exposes enough evidence for a user or judge to understand the next-question logic**

In this design, the center of gravity is the interview planner, while turn evaluation and coaching support that planner.

---

## 4. Core strategy: Planner-first balanced architecture
The interview loop should evolve from:

`Route -> Prompt -> LLM -> Response`

to:

`Context Build -> Planner State -> Turn Evaluation -> Planner Decision -> LLM Response -> Structured Turn Record`

The practical idea is simple:
- before the interview, build a grounded plan from CV and JD
- during the interview, update that plan with each answer
- after each answer, select the next question type and topic based on structured state
- after the session, synthesize coaching from structured records instead of raw transcript alone

This preserves low latency while making the AI behavior more defensible.

---

## 5. System components
The planner-first architecture should be described as four bounded units.

## 5.1 Context Builder
### Input
- CV text
- JD text
- selected interview mode

### Output
- candidate strengths
- candidate gaps
- priority topics
- prerequisite topics
- starter topics
- question plan seed

### Role
Turn CV and JD into a structured interview plan seed, not just a match score.

### Required improvement over current state
The current context layer is too shallow if it only returns overlap and missing skills. It must also generate a usable reason structure for planning.

---

## 5.2 Question Planner
### Input
- interview plan seed
- planner state
- prior turn history
- previous turn evaluation
- transcript reliability
- text-derived speaking cues

### Output
- next topic
- question strategy
- difficulty level
- follow-up mode
- why-selected trace

### Role
Decide what to ask next and why.

### Required planner behaviors
The planner must support at least these decisions:
- probe deeper into the same topic
- clarify a weak or ambiguous answer
- shift to a new gap topic
- recover to a prerequisite topic when the user struggles
- stretch difficulty upward when the user performs well

---

## 5.3 Turn Evaluator
### Input
- user answer text
- current target topic
- transcript quality signal
- lightweight speaking signals
- expected answer focus

### Output
- correctness
- depth
- communication
- topic relevance
- lightweight live cues for the UI

### Role
Provide structured signals that the planner can trust without requiring heavy per-turn analysis.

### Current-code alignment
This should extend the existing `turn_evaluation` and transcript/speaking analysis already returned through the interview response headers, rather than inventing a second parallel scoring path.

### Latency rule
This unit must remain lightweight enough for live interview use. It should avoid deep offline-style analysis inside the turn loop.

---

## 5.4 Coaching Synthesizer
### Input
- structured turn records
- topic progression
- planner decisions
- interview context

### Output
- final 1-5 scores for correctness, depth, communication, and topic relevance
- strongest topics
- weak topics
- top 3 skills to improve
- short coaching notes

### Role
Turn the planner-driven interview into a real coaching workflow after the live session.

### Required improvement over current state
Post-session coaching should synthesize from structured turn records and structured score summaries, not from raw history alone.

### Current-code alignment
This should reuse the existing report flow and modal entrypoints instead of creating a new reporting surface from scratch.

---

## 6. Data flow
The target flow should work in four stages.

## 6.1 Stage A — Pre-interview planning
Run once before the session.

### Purpose
Create an `interview_plan` that explains what the interview should focus on.

### Suggested structured output
- `candidate_strengths`
- `candidate_gaps`
- `priority_topics`
- `prerequisite_map`
- `starter_questions`
- `question_plan_seed`

### Why it matters
This prevents the session from starting as a generic AI interview.

---

## 6.2 Stage B — Live turn loop
Run every turn.

### Purpose
Update the interview plan with fresh performance signals and choose the next question.

### Live sequence
`User answer -> transcript quality -> speaking signals -> turn evaluator -> planner update -> question selector -> short AI response`

### Per-turn outputs that must exist
- `turn_evaluation`
- `planner_decision`
- `why_selected`
- `topic_state`
- `next_topic`
- `live_cues`

### Current-code alignment
These fields should extend the current `analysis` payload returned through `X-Interview-Analysis`, so the frontend can keep consuming a single structured source of truth.

### Why it matters
This is the main visible proof that the system is planner-driven rather than prompt-driven.

---

## 6.3 Stage C — Post-turn memory
Run after each turn.

### Purpose
Store structured interview state instead of relying on transcript text alone.

### Required turn record fields
- `topic`
- `question_type`
- `correctness`
- `depth`
- `communication`
- `topic_relevance`
- `live_cues`
- `asked_because`
- `next_decision`
- `trace_id`

### Current-code alignment
The implementation should preserve compatibility with the existing chat history and trace flow, while adding a structured turn-record layer behind the current router behavior.

### Why it matters
This transforms the system from a chat log into an interview state machine.

---

## 6.4 Stage D — Post-session synthesis
Run after the session or at checkpoints.

### Purpose
Generate defensible coaching from the structured interview record.

### Output
- strongest topics
- weak topics
- repeated hesitation or shallow-answer zones
- recommended next-practice topics
- learning path summary

### Why it matters
This makes the final coaching more explainable and more aligned with the planner behavior the user already saw live.

---

## 7. Planner model
The planner should be mixed, not single-source.

## 7.1 Inputs the planner must combine
1. **CV/JD gap signals**
2. **Performance-adaptive signals from the live session**
3. **Transcript reliability and text-derived clarity signals**

This is the right balanced choice because:
- CV/JD gives grounding
- live performance gives adaptation
- transcript and clarity signals prevent over-judging unclear turns

## 7.2 Topic state model
Each topic should have a lightweight state:
- `unasked`
- `probing`
- `weak`
- `strong`
- `needs_followup`
- `completed`

The planner updates topic state after every turn.

## 7.3 Question strategy model
The planner must choose not only the next topic, but also the next question style:
- `opening`
- `deep_dive`
- `clarify`
- `scenario`
- `recovery`
- `stretch`

This is important because asking about the right topic in the wrong way still feels unintelligent.

## 7.4 Why-selected trace
Every planner decision must include a concise explanation source such as:
- `gap_in_jd`
- `previous_answer_shallow`
- `prerequisite_missing`
- `confidence_recovery`
- `strong_performance_raise_difficulty`

This trace should be short, structured, and UI-safe.

---

## 8. Explainability requirements
The system should clearly explain these things:
1. why the interview focused on certain topics before the session
2. why this question was selected now
3. whether the user answered correctly, deeply, clearly, and on-topic
4. when the system chose to clarify instead of judge strongly
5. what the top 3 next practice skills should be after the session

Explainability should be visible through concise cards and structured summaries, not through a giant trace screen.

---

## 9. UI proof points
To support the Level 5 claim, the interview UI should expose a small number of visible planner signals.

## 9.1 Live planner cards
Recommended cards:
- `Current focus`
- `Why this question`
- `Next skill being tested`

## 9.2 Turn-quality cards
Recommended lightweight cards:
- `On-topic`
- `Needs more depth`
- `Clear communication`
- `Follow-up triggered`

These are cues, not per-turn hard scores. During the live interview, the UI should feel informative without looking like a grading dashboard.

## 9.3 Session-intent preview
At the start of the interview, show a short plan preview such as:
- the main focus areas
- the top gaps being tested
- the likely progression of topics

### Why these UI elements matter
Without visible proof points, the architecture may still look like advanced prompting. These cards make the planner behavior legible in seconds.

---

## 10. Scope boundaries
### In scope
- planner-first interview design
- mixed planning from CV/JD plus live performance
- structured turn records
- low-latency turn evaluation
- visible why-selected evidence in UI
- post-session coaching from structured records

### Out of scope
- heavy multimodal scoring inside every live turn
- full custom speech model stack
- large multi-agent orchestration framework
- recruiter-side product redesign
- deep Korea-specific feature set as a core engine requirement

This keeps the design focused, believable, and buildable.

---

## 11. Testing strategy
The design should be testable at three layers.

## 11.1 Planner logic tests
Test that the planner:
- builds valid priority topics and prerequisite maps
- chooses the correct follow-up mode
- transitions topic states correctly
- raises or lowers difficulty appropriately

## 11.2 Turn evaluation tests
Test representative answer types:
- strong but short
- long but shallow
- off-topic
- low-confidence transcript
- skipped answer
- recovery answer after a weak turn

## 11.3 End-to-end interview scenarios
Maintain demo-grade scenarios for:
1. strong candidate path
2. gap-focused path
3. prerequisite recovery path
4. low-quality transcript clarification path

These scenarios are important because the product claim depends on visible behavior, not just isolated unit logic.

---

## 12. Rollout strategy
The implementation should progress in four phases.

## Phase 1 — Backend structure
- separate planner/orchestrator concerns from the router
- define `interview_plan`, `planner_state`, `turn_record`, and `planner_decision`
- keep existing API behavior stable

## Phase 2 — Response schema proof
- return planner and turn-evaluation data in API responses
- expose `why_selected`, `topic_state`, `next_topic`, and `live_cues`
- let frontend consume these fields through the existing analysis-header flow without full UI polish yet

## Phase 3 — UI proof points
- add live planner cards
- add lightweight turn-quality cues instead of visible per-turn numeric scoring
- add session-intent preview

## Phase 4 — Post-session coaching
- generate the final report from structured turn records
- show final 1-5 scores for correctness, depth, communication, and topic relevance
- show top 3 skills to improve
- keep the existing report modal flow as the main presentation surface

This rollout order supports both demo readiness and technical clarity.

---

## 13. Success criteria
The design should be considered successful if it meets three kinds of goals.

## 13.1 Product success
- questions feel relevant to the user’s CV and target job
- the AI avoids random or repetitive topic selection
- weak answers trigger better follow-up or prerequisite recovery

## 13.2 Technical success
- planner state is separated from the route handler
- every turn yields structured decision traces
- post-session synthesis uses structured turn records
- live latency remains good enough for a smooth interview demo

## 13.3 Pitch success
The team can credibly say:
1. We do not ask questions randomly.
2. The planner combines CV/JD gaps with live answer quality.
3. Each next question is selected for a visible reason.

If these three statements are supported by working product behavior, SpeakCV will have a much stronger Level 5-capable interview story.

---

## 14. Final recommendation
SpeakCV should prioritize a **planner-first balanced upgrade** for the interview flow.

The shortest believable path toward Level 5 is:
1. turn CV/JD into a structured interview plan
2. separate question planning into its own decision layer
3. store structured turn state after every answer
4. expose why-selected and topic progression in the UI
5. generate final coaching from structured records rather than raw history alone

This creates a strong three-part narrative:
- **grounded before interview**
- **adaptive during interview**
- **explainable after interview**

That is the most practical way for SpeakCV to move beyond an LLM wrapper and toward a more credible Level 5 interview system.