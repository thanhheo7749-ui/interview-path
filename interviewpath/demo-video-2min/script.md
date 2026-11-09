# InterviewPath — 2-Minute Product Demo Script (English VO)

**Video file:** `interviewpath_demo_2min_silent.mp4` (1920x1080, 118s, silent — no audio track)
**Audience:** works for both investors/judges and HR customers.
**How to use:** read each line starting at its timestamp while the matching screen is showing, then record/mux your voice over the silent video (see "How to add your voice" below).

---

## 0:00 — Segment 1: AI screens every CV against your criteria
*(screen: Candidate Board with real uploaded CVs, sorted with reasons)*

> It's Monday morning. Mai has two hundred new CVs in her inbox.
> InterviewPath's AI has already screened every one against her hiring criteria —
> skills, experience, culture fit — and sorted them with a plain-language reason
> for every call.

## 0:27 — Segment 2: AI writes the job description
*(screen: JD Studio, AI-generated draft + Assistant panel)*

> A new role opens on her team. Instead of a blank page, InterviewPath's AI
> drafts a complete job description, pulled straight from her company's real
> standards.

## 0:47 — Segment 3: AI finds your best hiring channels
*(screen: Channel Intelligence table — LinkedIn, TopCV, referrals)*

> InterviewPath's Channel Intelligence breaks down every application by source —
> LinkedIn, TopCV, referrals — showing exactly which channel brings people she
> actually approves, and at what cost.

## 1:05 — Segment 4: Internal AI Copilot for company policy
*(screen: Copilot answering a leave-policy question, flagging a source conflict)*

> Employees stop pinging HR for every small question. They ask InterviewPath's
> Copilot directly, and it answers from the real handbook, citing sources —
> even flagging it when two policies disagree.

## 1:23 — Segment 5 (closing): Candidate-side differentiator + tagline
*(screen: "Polish & Shadow" AI interview coaching live demo)*

> And the candidates she's shortlisted don't walk in cold. InterviewPath coaches
> them through real mock interviews, polishing rough answers into confident ones.
>
> Screening. Writing. Insight. Support.
>
> InterviewPath — hire smarter, onboard faster.

*(video ends ~1:58)*

---

## How to add your voice

**Option A — record over the video while watching it:**
Open the mp4, read each line when its timestamp appears, record your mic separately
(phone voice memo or OBS), then mux:
```bash
ffmpeg -i interviewpath_demo_2min_silent.mp4 -i your_voice.mp3 \
  -c:v copy -c:a aac -shortest interviewpath_demo_2min_final.mp4
```

**Option B — once you have a paid TTS key (MiniMax or Gemini with billing enabled):**
Ask Claude to regenerate `narration.mp3`/`narration.wav` from this same script text and
mux it the same way — the visuals and timing don't need to change.

---

## Source screenshots
All five screens were captured live from the running InterviewPath app
(`hr@daehan-precision.sample` demo company), not static mockups:
- `screenshots/01-cv-screening.png`
- `screenshots/02-jd-studio.png`
- `screenshots/03-channel-intelligence.png`
- `screenshots/04-copilot.png`
- `screenshots/05-polish-and-shadow.png`
