# SpeakCV Interview-First Level 5 Design

## 1. Goal
SpeakCV should evolve into an **Interview-first Level 5-capable AI Interview Prep Coach**.

The core engine is not CV analysis. The core engine is the **interview loop**:
1. build context before the interview,
2. plan good questions,
3. evaluate each answer with lightweight signals in real time,
4. generate coaching and learning guidance.

CV and JD remain important, but only as **context feeders** that help the interview engine ask smarter questions and evaluate answers more accurately.

This design must also preserve demo usability:
- pre-interview analysis can be heavier
- per-turn analysis must stay lightweight
- post-interview analysis can be deeper

That is how SpeakCV can aim for Level 5 without becoming too slow during live usage.

---

## 2. Product positioning
SpeakCV should be presented as:

> An AI Interview Prep Coach with a structured interview loop that combines CV/JD context, lightweight turn-by-turn evaluation, and explainable coaching outputs.

This positioning is stronger than presenting SpeakCV as:
- a generic AI interviewer
- a CV analyzer with an interview add-on
- a broad career assistant with too many equal features

Because it makes the product feel:
- focused
- practical
- explainable
- technically coherent
- easier to trust during a live interview flow

---

## 3. What Level 5 means in this version
Level 5 here does not mean building a huge all-at-once multi-agent platform.

Instead, SpeakCV can credibly aim for Level 5 if:
1. LLM is not the only decision layer
2. interview turns include specialist signals beyond prose generation
3. question selection, answer evaluation, and coaching are clearly separated functions
4. the system exposes enough reasoning to show why it asked, judged, and coached the way it did

So the Level 5 story is concentrated inside the interview loop, not spread evenly across all product features.

---

## 4. Core design: Full interview loop with low-latency orchestration
The system should run in 3 stages.

## 4.1 Stage A — Pre-interview context build
Run once before the session begins.

### Purpose
Use CV + JD to create structured context for the interview.

### Output
- highlighted strengths
- skill gaps
- target topics
- expected difficulty areas
- interview focus suggestions

### Why it matters
This gives the interview engine a grounded starting point, so it does not ask generic questions.

### Latency rule
This stage can afford to be a little heavier because it runs once, not every turn.

---

## 4.2 Stage B — Real-time interview turn loop
Run on every turn, but stay lightweight.

### Purpose
For each user answer:
1. assess transcript reliability from post-STT text
2. assess lightweight speaking signals from text
3. evaluate answer quality
4. choose follow-up behavior
5. produce a concise next response

### Turn evaluator dimensions
Each turn should evaluate at least 3 dimensions:
1. **Technical correctness**
2. **Depth and reasoning**
3. **Communication quality**

The intended weighting is:
- technical correctness is core
- depth and reasoning is the differentiator
- communication quality supports coaching

### Latency rule
Per-turn logic must stay fast.
That means:
- no heavy deep analysis every turn
- no large offline-style evaluation inside the loop
- only lightweight scoring and routing inside the live path

---

## 4.3 Stage C — Post-interview synthesis
Run after the session or at checkpoints.

### Purpose
Generate deep, useful coaching from the full interview record.

### Output
- strengths summary
- recurring mistakes
- unanswered or weak topics
- communication notes
- learning path / next-practice plan

### Why it matters
This is where SpeakCV becomes a real prep coach rather than just a question-answer bot.

### Latency rule
This stage can be more detailed because it is not blocking the live interaction.

---

## 5. System components
The interview-first architecture should be described as 4 clear units.

## 5.1 Interview Context Builder
### Input
- CV
- JD

### Output
- strengths
- skill gaps
- target topics
- interview focus context

### Role
Feeds the whole interview loop with relevant context.

## 5.2 Question Planner
### Input
- interview context
- current topic
- prior turns
- previous answer quality

### Output
- next question
- follow-up strategy
- topic shift decision

### Role
Prevents the AI from asking random or repetitive questions.

## 5.3 Turn Evaluator
### Input
- user answer text
- transcript quality signal
- lightweight speaking signals
- current topic
- expected answer focus

### Output
- correctness signal
- depth signal
- communication signal
- uncertainty or hesitation signal

### Role
This is the main Level 5 proof inside the real-time loop.

## 5.4 Coaching Summarizer
### Input
- full turn history
- turn-level scores
- interview context

### Output
- detailed feedback
- improvement suggestions
- next practice topics

### Role
Turns the interview into a real learning workflow.

---

## 6. Role of CV and JD
CV and JD should stay in the system, but as supporting inputs.

### What they should do
- give context before the session
- influence question planning
- influence what gaps the evaluator pays attention to
- support final coaching output

### What they should not do
- overshadow the interview loop
- become the main proof point of the product
- force the UI to turn into a CV-heavy experience

This keeps the product centered on interview preparation while still making use of strong input context.

---

## 7. Explainability requirements
The system should explain at least these things clearly:
1. why the interview focused on certain topics
2. what the user answered correctly
3. where the answer lacked depth
4. where the answer sounded hesitant or unclear
5. what to improve next

Explainability should not require a giant trace UI.
It can be shown through concise summary blocks and structured coaching sections.

---

## 8. Korean-compatible framing
The product does not need to become deeply Korea-specific at the feature level.

It only needs to present qualities that are persuasive in that context:
- professionalism
- consistency
- non-magical AI logic
- explainable evaluation
- clear usefulness for interview readiness

So Korean compatibility should stay as a **trust and polish layer**, not the central engine design.

---

## 9. Scope boundaries
### In scope
- interview-first product framing
- low-latency interview loop design
- CV/JD as context feeder
- turn-by-turn evaluation logic
- post-interview coaching synthesis

### Out of scope
- full custom speech model stack
- heavy per-turn multimodal analysis
- full recruiter-side product pivot
- large multi-agent platform build before demo

This keeps the design focused and believable.

---

## 10. Final recommendation
SpeakCV should stop treating CV analysis and interview intelligence as equal pillars.

The better strategy is:
1. make interview preparation the clear core
2. use CV + JD to make the interview smarter
3. keep the live loop fast with lightweight evaluation
4. move deeper analysis to pre-interview and post-interview stages
5. present the whole system as an explainable, structured interview coaching engine

That gives SpeakCV the strongest combination of:
- product focus
- live demo quality
- technical credibility
- and a realistic Level 5 story.
