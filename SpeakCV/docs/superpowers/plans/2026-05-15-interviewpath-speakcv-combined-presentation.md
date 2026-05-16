# InterviewPath + SpeakCV Combined Presentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Revise one presentation script file so InterviewPath stays the big platform story while SpeakCV becomes the main proof-point demo section.

**Architecture:** Keep the work in a single markdown script so the presenter rehearses from one source of truth. Restructure the script in one pass: shorten the broad platform narration, add a clear transition into SpeakCV, expand the SpeakCV section as the longest proof point, and reconnect that demo back to the larger InterviewPath message in the closing.

**Tech Stack:** Markdown, approved presentation design spec, existing InterviewPath script content, existing SpeakCV script content

---

## File structure

- Modify: `docs/superpowers/2026-05-15-speakcv-chat-demo-presentation-script.md` — unified English presentation script
- Reference: `docs/superpowers/specs/2026-05-15-interviewpath-speakcv-combined-presentation-design.md` — approved combined presentation strategy

---

### Task 1: Restructure the script around the platform-to-proof-point story

**Files:**
- Modify: `docs/superpowers/2026-05-15-speakcv-chat-demo-presentation-script.md`
- Reference: `docs/superpowers/specs/2026-05-15-interviewpath-speakcv-combined-presentation-design.md`

- [ ] **Step 1: Replace the current opening with InterviewPath-first framing**

```md
## Main presentation script

### 1. Opening
Introduce InterviewPath as the larger platform.
State early that today’s focus is SpeakCV as one of the clearest proof points inside that platform.
```

- [ ] **Step 2: Add a shorter platform context section before the demo focus**

```md
### 2. The problem and big idea
Cover the HR problem, the candidate problem, and the Candidate Passport / living profile idea in a shorter form than the broad deck.

### 3. The bigger platform view
Briefly explain the platform flow, such as workflow automation, hiring intelligence, and the full candidate journey.
Keep this section high-level.
```

- [ ] **Step 3: Add a clean transition from InterviewPath to SpeakCV**

```md
### 4. Transition to SpeakCV
Use a direct bridge such as:
"That is the bigger picture of InterviewPath. Now I want to zoom in on one part that makes this value easiest to see in action: SpeakCV."
```

- [ ] **Step 4: Expand the SpeakCV section into the longest proof-point block**

```md
### 5. SpeakCV demo focus
Cover:
- what SpeakCV is
- why generic interview tools feel weak
- setup with CV/JD/context
- chat flow
- why the next question feels relevant
- coaching/report value
```

- [ ] **Step 5: Reconnect the SpeakCV demo back to the platform story in the ending**

```md
### 6. Reconnecting to InterviewPath
Explain that SpeakCV is useful by itself, but also strengthens InterviewPath by generating candidate signals, feedback, and progress memory.

### 7. Closing
Return to the main message: InterviewPath is the larger platform, and SpeakCV is the clearest live proof shown today.
```

---

### Task 2: Smooth the language for live speaking

**Files:**
- Modify: `docs/superpowers/2026-05-15-speakcv-chat-demo-presentation-script.md`

- [ ] **Step 1: Rewrite any section that sounds too formal or too technical**

Use this rule while editing:

```md
- Prefer common words
- Keep sentences short
- Keep the tone friendly and confident
- Sound like a builder explaining a real product
```

- [ ] **Step 2: Make the platform sections shorter than the SpeakCV section**

Check these exact expectations:

```md
- Opening and platform context should move quickly
- SpeakCV should be the most concrete and detailed section
- Closing should be short and strong
```

- [ ] **Step 3: Update the optional bridge lines so they match the new combined flow**

```md
Bridge lines should support:
- moving from big platform story to focused demo
- pausing after the first SpeakCV explanation
- emphasizing why the next question logic matters
- reconnecting the demo back to the larger platform
```

---

### Task 3: Final content review

**Files:**
- Modify: `docs/superpowers/2026-05-15-speakcv-chat-demo-presentation-script.md`

- [ ] **Step 1: Check the script against the approved combined design**

```md
Confirm the script clearly shows:
- InterviewPath is the larger platform
- SpeakCV is the standout proof point
- the platform-to-demo transition is smooth
- the ending reconnects SpeakCV to the broader platform story
```

- [ ] **Step 2: Remove any lines that overclaim unsupported product behavior**

```md
Avoid:
- deep technical claims not needed for the demo
- making SpeakCV sound fully separate from InterviewPath
- giving equal weight to every platform component
```

- [ ] **Step 3: Read for presentation flow and rhythm**

Use this checklist:

```md
- easy to read aloud
- no abrupt jumps between sections
- strongest energy saved for the SpeakCV demo portion
- ending feels like a conclusion to the whole platform story
```

---

## Self-review

### Spec coverage
- InterviewPath-first framing: covered by Task 1
- clear zoom into SpeakCV: covered by Task 1
- SpeakCV as main proof-point section: covered by Task 1 and Task 2
- reconnection back to the larger platform: covered by Task 1 and Task 3
- simple spoken English: covered by Task 2

### Placeholder scan
No TBDs, TODOs, or deferred implementation notes are included.

### Type consistency
All tasks modify one file only: `docs/superpowers/2026-05-15-speakcv-chat-demo-presentation-script.md`.
