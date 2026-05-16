# SpeakCV Chat Demo Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Draft a clear English demo script package for the SpeakCV chat/interview flow, including a full script, a shorter practice version, and optional bridge lines for extending to 10-15 minutes.

**Architecture:** Keep everything in one focused markdown file so the presenter can rehearse from a single source of truth. Build the package in three layers: full script first, shorter practice version second, and optional bridge lines last so the talk can scale without changing the core message.

**Tech Stack:** Markdown, existing SpeakCV spec context, simple spoken English

---

## File structure

- Create: `docs/superpowers/scripts/2026-05-15-speakcv-chat-demo-script.md` — final deliverable containing the full script, shorter version, and bridge sentences
- Reference: `docs/superpowers/specs/2026-05-15-speakcv-chat-demo-script-design.md` — approved design constraints and audience/tone guidance

---

### Task 1: Draft the full English demo script

**Files:**
- Create: `docs/superpowers/scripts/2026-05-15-speakcv-chat-demo-script.md`
- Reference: `docs/superpowers/specs/2026-05-15-speakcv-chat-demo-script-design.md`

- [ ] **Step 1: Create the markdown file with the approved section structure**

```md
# SpeakCV Chat Demo Script

## 1. Full demo script
### Opening
### Problem
### Demo flow
### Closing

## 2. Shorter practice version

## 3. Optional bridge sentences for 10-15 minutes
```

- [ ] **Step 2: Write the full script in simple spoken English**

Include these content rules directly in the script:

```md
- Keep sentences short.
- Use common words.
- Explain SpeakCV as an interview coach, not just a chatbot.
- Mention CV/JD context, relevant follow-up questions, and post-session coaching.
- Keep the tone natural, calm, and easy to say out loud.
```

- [ ] **Step 3: Make sure the full script follows the approved demo order**

```md
1. Opening: what SpeakCV is
2. Problem: why generic mock interviews are weak
3. Setup: CV, JD, or interview context
4. Live chat: answer, AI response, next question
5. Logic: why the next question is relevant
6. Outcome: coaching/report value
7. Closing: summarize user value
```

- [ ] **Step 4: Self-check the full script against the spec**

Check for these exact points:

```md
- Mixed audience language
- Simple, safe English
- Balanced emphasis across chat flow, reasoning, personalization, and coaching
- No claims beyond the current product direction
```

---

### Task 2: Add the shorter practice version

**Files:**
- Modify: `docs/superpowers/scripts/2026-05-15-speakcv-chat-demo-script.md`

- [ ] **Step 1: Add a shorter version under its own heading**

```md
## 2. Shorter practice version
```

- [ ] **Step 2: Compress the same message into a faster rehearsal script**

Keep these constraints:

```md
- Preserve the same main message
- Remove repetition
- Keep it easier to memorize
- Make it usable as a 5-7 minute speaking version
```

- [ ] **Step 3: Verify the shorter version still covers the essential points**

```md
Required points:
- what SpeakCV is
- why generic interview tools are not enough
- how the chat flow works
- why the next question feels relevant
- what value the user gets at the end
```

---

### Task 3: Add optional bridge sentences for 10-15 minutes

**Files:**
- Modify: `docs/superpowers/scripts/2026-05-15-speakcv-chat-demo-script.md`

- [ ] **Step 1: Add a final section for optional bridge lines**

```md
## 3. Optional bridge sentences for 10-15 minutes
```

- [ ] **Step 2: Write bridge lines grouped by where they can be inserted**

Use these groups:

```md
- Before the setup
- After the first AI response
- Before explaining why the next question matters
- Before the coaching/report section
- Before the closing
```

- [ ] **Step 3: Keep each bridge line optional and easy to insert live**

Use this style rule:

```md
Each bridge should be 1-3 short sentences, sound natural when spoken alone, and not depend on exact UI wording.
```

- [ ] **Step 4: Final package review**

Check the final file for these issues:

```md
- hard words that are awkward to pronounce
- repeated ideas that make the talk drag
- technical claims that non-technical listeners may not follow
- missing transitions between major sections
```

---

## Self-review

### Spec coverage
- Full English demo script: covered by Task 1
- Shorter practice version: covered by Task 2
- Optional bridge sentence set for 10-15 minutes: covered by Task 3
- Mixed-audience, simple-English constraint: covered across all three tasks

### Placeholder scan
No TBDs, TODOs, or deferred implementation notes are included.

### Type consistency
All deliverables point to one final output file: `docs/superpowers/scripts/2026-05-15-speakcv-chat-demo-script.md`.
