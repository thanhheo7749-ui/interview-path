<!-- ppt-master-schema: design-spec/v1 -->
# InterviewPath (Team Zenith - HUTECH) - Design Spec

## I. Project Information

| Item | Value |
| --- | --- |
| Project Name | InterviewPath — AI4Biz 2026 Track 1 (Team Zenith - HUTECH) |
| Canvas Format | PPT 16:9 (1280×720) |
| Page Count | 11 |
| Primary Language | en-US |
| Target Audience | AI4Biz 2026 Judges (enterprise executives, HR directors, AI & engineering leaders) evaluating business fit, AI rigor, and working MVP completeness |
| Communication Intent | Expose the broken links in keyword-based hiring and handbook onboarding first, then persuade judges that InterviewPath solves all 4 Track 1 requirements end-to-end with a working 4-container MVP |
| Desired Audience Outcome | Judges grasp the 'Paper CVs are claims, spoken answers are proof' thesis at a glance through airy orchestrator-and-node diagrams and live UI proof, awarding top marks for business value and MVP bonus |
| Core Message / Ask / Action | InterviewPath turns static company handbooks into a living Knowledge Graph powering policy-checked JDs, pass-rate channel ROI, adaptive Voice AI screening ('Hidden Gems'), 30-60-90 onboarding, and conflict-aware RAG — cutting HR admin hours by 78% |
| Delivery Context | Hybrid: standalone English PDF submission (max 15 slides, deadline 13/11/2026) plus 15-minute live English Final Pitch by 3 members with a 2-minute demo video and 5-minute Q&A on 19/11/2026 |
| Artifact Afterlife | Official submission archive in folder AI4Biz_Zenith_2026 (.pdf + natively animated .pptx for final stage presentation) |
| Reading Mode | presentation |
| Content Strategy | Preserve all 10 required competition sections in exact order (splitting section 8 Mockup/Demo across Slides 08 and 09 for large readable screenshots) while expressing workflows through minimalist circular journey nodes, curved dashed n8n-style connectors, and floating pill badges |
| Design Style | Legacy Minimalist Orchestrator Flow (100% pure white #FFFFFF open canvas, generous whitespace, rounded pill tags, electric blue #2563EB + AI purple #7C3AED + verified emerald #059669 circular nodes, curved dashed Bezier connectors, and native PowerPoint choreography) |
| AI Image Acquisition Path | none |
| Generation Mode | continuous |
| Spec Refinement | disabled |
| Speaker Notes | disabled — explicit user confirmation in Stage 2 |
| Custom Animations | enabled — explicit user request in revision round |
| Narration Audio | disabled — explicit user confirmation in Stage 2 |
| Created Date | 2026-11-12 |

## II. Canvas Specification

| Property | Value |
| --- | --- |
| Format | PPT 16:9 |
| Dimensions | 1280 × 720 |
| viewBox | `0 0 1280 720` |
| Margins | 68px left/right, 40px top, 44px bottom |
| Content Area | `x=68..1212, y=40..676` (1144 × 636) |

## III. Visual Theme

### Theme Style

- **Mode**: custom
- **Mode References**: showcase, narrative
- **Mode Behavior**: Advance from fragmented hiring pain to the Talent Memory breakthrough and closed-loop orchestration using open minimalist showcase scale — each slide centers on an airy node-and-connector flow, light AI Command Center, or browser-framed live UI proof with crisp 2-to-5-word labels.
- **Visual style**: custom
- **Visual Style References**: soft-rounded, swiss-minimal
- **Visual Style Behavior**: Pure white #FFFFFF open canvas across all 11 slides with generous breathing room, soft pill tags (`rx=16`), bold `#0F172A` display titles paired with light `#64748B` subtitles, dark `#0F172A` orchestrator hubs, circular `3px`-bordered journey nodes (`#2563EB`, `#7C3AED`, `#059669`) with numbered badges and soft outer halos, curved dashed Bezier flow lines (`stroke-dasharray="6,5"`), and discreet top-right HUTECH University emblem + bottom-right slide numeral.
- **Theme**: AI Talent Memory Flow — electric blue, violet memory, and emerald verification nodes linked by n8n-style dashed pathways on a spotless white studio field.
- **Tone**: Modern SaaS product pitch, effortless clarity, transparent white-box engineering.

### Color Scheme

| Role | HEX | Purpose |
| --- | --- | --- |
| Background | #FFFFFF | Mandatory 100% pure white open slide field across all 11 slides |
| Secondary background | #F8FAFC | Subtle light slate brain core, comparison surfaces, and quiet zones |
| Surface | #EFF6FF | Soft electric-blue tag pills and active highlights |
| Primary | #2563EB | Electric Blue for active journey nodes, headers, and primary signals |
| Accent | #7C3AED | AI Memory Purple for Talent Memory, Hidden Gem highlights, and orchestrator badges |
| Secondary accent | #059669 | Verified Emerald Green for audited outputs, hired state, and competitive advantage |
| Positive | #059669 | Verified pass badges, savings deltas, and advantage checkmarks |
| Warning | #D97706 | Partial capability alerts, channel warnings, and policy disagreement flags |
| Negative | #EF4444 | Broken recruitment links, manual bottlenecks, and legacy ATS gaps |
| Body text | #0F172A | Deep slate ink for headlines, orchestrator pills, and primary node titles |
| Secondary text | #64748B | Muted slate for 1-line subtitles, captions, and slide numerals |
| Divider | #E2E8F0 | Clean 1px borders, subtle card hairlines, and connector tracks |

### AI Image Strategy

- **Image Rendering**: none

## IV. Typography System

### Font Plan

| Role | Character (Reference) | Primary | English if non-English | Fallback tail |
| --- | --- | --- | --- | --- |
| Title | Clean geometric-humanist display sans | Trebuchet MS | Trebuchet MS | sans-serif |
| Body | Crisp modern UI & presentation sans | Calibri | Calibri | sans-serif |
| Code | Technical port and candidate ID mono | Consolas | Consolas | monospace |

- **Role rationale**: `Code` (`Consolas`) renders Docker container ports (`:5174`, `:3001`, `:8001`, `:3307`) and candidate IDs (`#A5`, `#A6`) with engineering precision.
- **Title stack**: Trebuchet MS
- **Body stack**: Calibri
- **Code stack**: Consolas

### Font Size Hierarchy

| Purpose | Anchor Size (px) |
| --- | ---: |
| Cover title | 68 |
| Hero number | 46 |
| Title | 40 |
| Subtitle | 19 |
| Body | 20 |
| Card title | 18 |
| Annotation | 15 |
| Footnote | 13 |

## V. Layout Principles

### Deck-wide Direction

- **Hierarchy direction**: Top-left rounded section tag + bold `#0F172A` headline + 1-line `#64748B` subtitle (paired with uncropped HUTECH University logo top-right) → open minimalist node/orchestrator diagram or browser-framed UI showcase floating on pure `#FFFFFF` → clean bottom-right slide numeral (`01`..`11`) and subtle Team Zenith attribution.
- **Composition tendency**: Prefer open-canvas circular icon nodes, dark `#0F172A` / glowing `#7C3AED` hubs, curved dashed Bezier flow connectors, zig-zag floating white action badges, left-accented `.ai-step-box` signal pills, macOS browser frames for live screenshots, and `VS` advantage columns over heavy enclosed card grids.
- **Cross-page continuity**: 100% `#FFFFFF` canvas, consistent pill tags, recurring circular node & dashed flow language, uncropped HUTECH emblem, and coordinated native PowerPoint transitions + automatic click-free element cascades.
- **Spacing posture**: Airy, uncluttered `legacy.html` generosity (`68px` horizontal margins, ample open white space around circular nodes and curved paths).
- **Spacing anchors**: `68px` page margin, `20px` block gap, `24px` column gutter, `16px` corner radius, `1.35` body leading.

## VI. Icon Usage Specification

- **Primary bundled library**: phosphor-duotone
- **Brand-logo library**: simple-icons

| Icon Path | Suitable Scenarios |
| --- | --- |
| `phosphor-duotone/file-text` | |
| `phosphor-duotone/microphone` | |
| `phosphor-duotone/brain` | |
| `phosphor-duotone/chart-bar` | |
| `phosphor-duotone/users` | |
| `phosphor-duotone/sketch-logo` | |
| `phosphor-duotone/check-circle` | |
| `phosphor-duotone/warning` | |
| `phosphor-duotone/x-circle` | |
| `phosphor-duotone/lightning` | |
| `phosphor-duotone/database` | |
| `phosphor-duotone/buildings` | |
| `phosphor-duotone/user-check` | |
| `phosphor-duotone/compass` | |
| `phosphor-duotone/sparkle` | |
| `phosphor-duotone/arrow-right` | |
| `phosphor-duotone/clock` | |
| `phosphor-duotone/shield-check` | |
| `phosphor-duotone/git-branch` | |
| `phosphor-duotone/chats` | |
| `phosphor-duotone/funnel` | |
| `phosphor-duotone/magnifying-glass` | |
| `phosphor-duotone/robot` | |
| `phosphor-duotone/identification-card` | |
| `phosphor-duotone/calendar-check` | |
| `phosphor-duotone/handshake` | |
| `phosphor-duotone/stack` | |
| `phosphor-duotone/gear` | |
| `phosphor-duotone/arrows-clockwise` | |
| `phosphor-duotone/briefcase` | |
| `simple-icons/docker` | |
| `simple-icons/react` | |
| `simple-icons/nextdotjs` | |
| `simple-icons/fastapi` | |
| `simple-icons/mysql` | |

## VII. Visualization Reference List

| Page | Family | Template | Usage |
| --- | --- | --- | --- |
| P10 | chart | dumbbell_chart | Compare manual HR hours (32.5h) against InterviewPath AI hours (5.5h) across 4 hiring stages |
| P11 | table | feature_matrix | Contrast InterviewPath against Legacy ATS and Point AI Tools across 6 enterprise capabilities |

## VIII. Image Resource List

| Filename | Dimensions | Ratio | Purpose | Type | Image pattern | Crop Policy | Acquire Via | Status | Reference | text_policy | page_role |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `hutech_logo.png` | 2000×641 | 3.12 | HUTECH University official emblem on cover and top-right header | Brand Logo | Uncropped university header badge and cover emblem | no-crop | user | Existing | Official HUTECH University horizontal logo | none | local |
| `s1_knowledge_graph.png` | 1280×800 | 1.60 | Live MVP screenshot of Company Knowledge Graph | Screenshot | Exact 1.60 uncropped browser frame in Slide 08 top-left quadrant | no-crop | user | Existing | Live InterviewPath HR Portal showing Daehan Precision Vina interactive Knowledge Graph | none | local |
| `s1_jd_studio.png` | 1280×800 | 1.60 | Live MVP screenshot of AI JD Studio & policy check | Screenshot | Exact 1.60 uncropped browser frame in Slide 08 top-right quadrant | no-crop | user | Existing | Live InterviewPath JD Studio mapping Knowledge Graph must-have nodes | none | local |
| `s1_channel_intel.png` | 1280×800 | 1.60 | Live MVP screenshot of Channel Quality Attribution | Screenshot | Exact 1.60 uncropped browser frame in Slide 08 bottom-left quadrant | no-crop | user | Existing | Live InterviewPath Channel Analytics comparing LinkedIn, TopCV, University, and Referrals | none | local |
| `s2_cv_screening_board.png` | 1280×800 | 1.60 | Live MVP screenshot of CV Hold & Magic-Link Override | Screenshot | Exact 1.60 uncropped browser frame in Slide 08 bottom-right quadrant | no-crop | user | Existing | Live InterviewPath Candidate Detail showing Marcus Vance (#A6) CV Hold and 1-Click Magic Link | none | local |
| `s2_live_ai_interview.png` | 1280×800 | 1.60 | Live MVP screenshot of Recorded Voice AI Interview Room | Screenshot | Exact 1.60 uncropped browser frame in Slide 09 top-left quadrant | no-crop | user | Existing | Live InterviewPath Recorded Voice AI Interview asking adaptive ISO 9001 follow-up question | none | local |
| `s3_hidden_gem_evidence.png` | 1280×800 | 1.60 | Live MVP screenshot of 2x2 Evidence Calibration Matrix surfacing Hannah Park | Screenshot | Exact 1.60 uncropped browser frame in Slide 09 top-right quadrant | no-crop | user | Existing | Live InterviewPath 2x2 Evidence Calibration Matrix highlighting Hidden Gem Hannah Park (#A5) | none | local |
| `s4_onboarding_roadmap.png` | 1280×800 | 1.60 | Live MVP screenshot of 30-60-90 Day Probation Plan | Screenshot | Exact 1.60 uncropped browser frame in Slide 09 bottom-left quadrant | no-crop | user | Existing | Live InterviewPath 30-60-90 Day Onboarding Plan ready for 1-click HR approval | none | local |
| `s5_policy_copilot.png` | 1280×800 | 1.60 | Live MVP screenshot of Internal Policy Copilot flagging SOURCES DISAGREE | Screenshot | Exact 1.60 uncropped browser frame in Slide 09 bottom-right quadrant | no-crop | user | Existing | Live InterviewPath Employee Copilot citing handbooks and alerting SOURCES DISAGREE | none | local |

## IX. Content Outline

### Part 1: Problem, Users & Core Insight

#### Slide 01 - Title (InterviewPath — Team Zenith)

- **Audience move**: Sees an ultra-clean minimalist SaaS hero slide with HUTECH University identity, gradient `InterviewPath` lockup, 4 connected Track-1 circular nodes, and Team Zenith members.
- **Relationships**: Four Track 1 circular nodes (`AI JD Studio`, `Channel ROI`, `Voice AI Screen`, `Policy Copilot`) connect horizontally beneath the `InterviewPath` gradient title, anchored by `Team Zenith` (`Lưu Gia Bảo`, `Tạ Hoàng Thành`, `Nguyễn Phương Quang`).
- **Cover impact**: Binding hook — `"AI Talent Memory & Evidence-First Recruitment Platform: From Company Handbooks & Spoken Proof to Day-90 Employees"`; Reference composition — centered `legacy.html` hero on pure `#FFFFFF` with blue-to-purple gradient title, 4 connected circular capability nodes, and minimalist Team Zenith pills.
- **Title**: InterviewPath
- **Core message**: AI Talent Memory Platform unifying recruitment screening, channel attribution, and day-one employee onboarding.
- **Content**:
  - Competition badge: `AI4BIZ 2026 · TRACK 1: HUMAN RESOURCES & RECRUITMENT`
  - Tagline: `AI Talent Memory Platform — Turning Handbooks & Spoken Proof into Smarter Hires`
  - Connected circular nodes: `1. AI JD Studio` · `2. Channel ROI` · `3. Voice AI Screen` · `4. Policy Copilot`
  - Team Zenith (`HUTECH University`): `Lưu Gia Bảo` · `Tạ Hoàng Thành` · `Nguyễn Phương Quang`
- **Motion suggestion**: Smooth fade-in of HUTECH badge, zoomed entrance on gradient title, staggered pop-in across the 4 connected circular nodes, and gentle rise-up on the Team Zenith bar.
- **Images**: `hutech_logo.png` (top cover emblem).

#### Slide 02 - 2. Business Problem

- **Audience move**: Recognizes why high-volume hiring breaks down across 4 open minimalist columns with broken dashed connectors.
- **Relationships**: Four broken operational stages (`Slow Disconnected JDs`, `Blind Channel Spend`, `Paper CV Keyword Bias`, `Conflicting Policy PDFs`) leak time, budget, and engineering talent during hiring surges.
- **Composition**: Open 4-column `legacy.html` minimalist icon-and-metric layout floating on pure `#FFFFFF` above a clean enterprise context strip.
- **Title**: Recruitment & Onboarding Are Fragmented
- **Core message**: Keyword CV filters reject real builders while disconnected JDs, blind ad spend, and conflicting PDF handbooks drain HR hours.
- **Content**:
  - `3–5 Days` · `Slow, Disconnected JDs` · Manual Word templates unlinked from engineering & ISO rules
  - `42% Waste` · `Blind Channel Spend` · Counting vanity clicks instead of verified Round-1 pass rates
  - `68% Missed` · `Paper CV Keyword Bias` · Rigid keyword filters auto-reject strong builders with concise CVs
  - `45m / Day` · `Handbook & Onboarding Chaos` · Generic checklists and silent contradictions across PDF policies
  - Context pill: `Occurs during 20–200+ role/year hiring waves in scaling Tech, SaaS & Manufacturing firms`
- **Motion suggestion**: Push/fade transition; title frames first, followed by sequential rise-up across the 4 broken-link columns and context strip.
- **Images**: `hutech_logo.png` (header).
- **Data class**: scenario

#### Slide 03 - 3. Target Business & Users

- **Audience move**: Sees one central Enterprise Hub fanning curved dashed connectors down to 4 circular user-role nodes and their `Pain → Gain` shifts.
- **Relationships**: Top-center `Mid-to-Large Enterprise Hub (100–2,000+ Staff)` connects via curved dashed lines to `1. HR & Talent`, `2. Candidates`, `3. Hiring Managers`, and `4. New Hires`.
- **Composition**: Orchestrator-to-nodes fan layout on pure `#FFFFFF` with dark `#0F172A` enterprise hub at top, curved dashed Bezier connectors, and 4 circular numbered user nodes above concise `✕ Pain` / `✓ Gain` pills.
- **Title**: 1 Enterprise Hub, 4 Underserved User Roles
- **Core message**: Built for scaling 100–2,000+ staff enterprises across Tech, SaaS, FinTech, and Precision Manufacturing.
- **Content**:
  - Top Hub: `Mid-to-Large Enterprises (100–2,000+ Staff)` · `Pilot Archetype: Daehan Precision Vina & Tech Teams`
  - `1. HR & Talent`: `✕ 200+ CVs & manual JDs` → `✓ 1-Click JD & Evidence Board`
  - `2. Job Candidates`: `✕ Black-box keyword reject` → `✓ Fit Compass & 24/7 Voice AI`
  - `3. Hiring Managers`: `✕ Unverified Round-2 interviews` → `✓ Citation-Backed Briefs`
  - `4. New Hires`: `✕ Conflicting PDF handbooks` → `✓ 30-60-90 Plan & Policy Copilot`
- **Motion suggestion**: Hub zooms in, curved dashed connectors wipe downward, and the 4 user role nodes pop in left-to-right.
- **Images**: `hutech_logo.png` (header).

#### Slide 04 - 4. Business Insight

- **Audience move**: Realizes hiring needs a living Talent Memory — paper CVs are unverified claims, whereas spoken technical answers are verifiable proof.
- **Relationships**: `Paper CV Fit` × `Spoken Technical Proof` forms a 2×2 Calibration Matrix spotlighting `Hidden Gem (Hannah Park #A5)`, paired with the core Talent Memory insight quote and 3 structural unlocks.
- **Composition**: Airy 2-column split on pure `#FFFFFF`: sleek 2×2 Matrix with glowing purple `Hidden Gem` highlight on the left, paired with a bold blue-purple breakthrough quote and 3 left-bordered `.ai-step-box` cards on the right.
- **Title**: Paper CVs Are Claims. Spoken Answers Are Proof.
- **Core message**: Cross-referencing resumes against adaptive spoken proof rescues 'Hidden Gems' and turns interview gaps into Day-1 onboarding plans.
- **Content**:
  - 2×2 Matrix: `Priority Hire` · `Over-Polished CV` · `★ Hidden Gem (Hannah Park #A5)` · `Low Fit`
  - Quote: `"Hiring cannot rely on a static CV — it requires a living AI Talent Memory."`
  - `01 · Keyword Blindness`: Concise CVs dropped → Adaptive Voice AI proves depth
  - `02 · Memory Reset`: Notes lost after offer → Interview gaps build 30-60-90 plans
  - `03 · Silent Policy Drift`: PDFs disagree → Copilot flags `SOURCES DISAGREE`
- **Motion suggestion**: 2×2 Matrix fades/zooms in with a subtle pulse on Hidden Gem, followed by the breakthrough quote and 3 staggered insight cards.
- **Images**: `hutech_logo.png` (header).

### Part 2: Solution, AI Architecture & Workflow

#### Slide 05 - 5. Proposed Solution

- **Audience move**: Grasps the entire `From Handbook & CV to Employee` journey at a glance via the signature `legacy.html` AI Orchestrator + curved n8n dashed lines + 8 circular nodes diagram.
- **Relationships**: Top-center `#0F172A` `AI Orchestrator (Living Knowledge Graph)` coordinates 8 sequential circular journey nodes (`1. Handbook & JD` through `8. Policy Copilot`) via curved dashed Bezier flows and floating action pills.
- **Composition**: Exact `legacy.html` Slide 05 signature layout on pure `#FFFFFF`: top dark navy `AI Orchestrator` pill + purple sub-pill, 8 curved dashed connectors with zig-zag floating white action badges, and 8 `3px`-bordered circular icon nodes along a horizontal dashed baseline.
- **Title**: From Handbook & CV to Day-90 Employee
- **Core message**: How the AI Orchestrator & Living Knowledge Graph manage the seamless recruitment-to-onboarding journey.
- **Content**:
  - Hub: `AI Orchestrator` · `Continuously coordinates, evaluates, and stores Talent Memory`
  - Floating badges: `Maps Policy` · `Tracks ROI` · `Overrides Hold` · `Probes Voice` · `Surfaces Gem` · `Cites Quotes` · `Builds Roadmap` · `Guards Policy`
  - 8 Circular Nodes: `1. Handbook & JD` · `2. Channel ROI` · `3. CV + Override` · `4. Voice AI Probe` · `5. 2×2 Hidden Gem` · `6. Round-2 Brief` · `7. 30-60-90 Plan` · `8. Policy Copilot`
- **Motion suggestion**: Orchestrator hub zooms in first, curved n8n connectors wipe downward from top to bottom, and circular nodes `1` to `8` pop in sequentially left-to-right.
- **Images**: `hutech_logo.png` (header).

#### Slide 06 - 6. How AI Helps

- **Audience move**: Sees inside the `AI Talent Memory Brain` (`Retrieve → Reason → Verify → Remember`) with all 4 AI4Biz Track 1 engines mapped cleanly between `1. Raw Signals` and `3. Verified Results`.
- **Relationships**: `orchestrator-hub` from Slide 05 morphs into the central `ai-brain-core` (`2×2 Track-1 modules + glowing central orb`), receiving `1. Raw Signals` from the left and emitting `3. Verified Results` to the right, closed by `4. Talent Memory Loop` below.
- **Composition**: Exact `legacy.html` Slide 06 Light AI Command Center on pure `#FFFFFF`.
- **Title**: How InterviewPath AI Thinks
- **Core message**: Retrieve → Reason → Verify → Remember across all 4 AI4Biz Track 1 HR & Recruitment pillars.
- **Content**:
  - `1. Raw Signals`: `Company Handbooks` · `Job Board Traffic` · `CV + Spoken Audio` · `Employee Queries`
  - `2. AI Talent Memory Brain`: `Track 1.1 Voice Prober` · `Track 1.2 Graph JD Studio` · `Track 1.3 Channel ROI` · `Track 1.4 Cited Policy RAG` + Central Glowing Brain Orb
  - `3. Verified Results`: `Compliant Job Post` · `Pass-Rate ROI Rank` · `2×2 Hidden Gem Brief` · `30-60-90 & Cited Answer`
  - `4. Talent Memory Loop`: `AI remembers interview gaps & probation results to improve every next hire.`
- **Motion suggestion**: Deterministic Morph transition pairing `orchestrator-hub` (P05) to `ai-brain-core` (P06), followed by left signals, directional chevrons, right results, and the bottom dashed memory loop pill.
- **Images**: `hutech_logo.png` (header).

#### Slide 07 - 7. How It Works

- **Audience move**: Traces concrete data handoffs across 5 connected circular stage columns from document upload to conflict-safe employee Q&A.
- **Relationships**: Five sequential circular stage nodes (`1. Setup` → `2. Screen` → `3. Calibrate` → `4. Onboard` → `5. Support`) each step vertically through `Trigger Input → AI Engine → Verified Output`.
- **Composition**: 5 open connected columns on pure `#FFFFFF` topped by numbered circular icon nodes on a dashed track, with clean color-coded pills underneath.
- **Title**: 5-Stage Execution: Input to Verified Output
- **Core message**: Transparent white-box pipeline with human-in-the-loop HR control at every stage.
- **Content**:
  - `1. Setup`: `Handbooks + Form` → `Graph + JD Studio` → `Published JD & Tracker`
  - `2. Screen`: `Marcus CV (#A6)` → `HR Override + Voice AI` → `Adaptive ISO Q&A`
  - `3. Calibrate`: `Hannah CV (#A5)` → `2×2 Matrix Engine` → `Hidden Gem + Brief`
  - `4. Onboard`: `'Hired' + Gaps` → `30-60-90 Generator` → `Approved Probation Plan`
  - `5. Support`: `Leave Policy Query` → `Cited RAG + Guardrail` → `Clause + Conflict Alert`
- **Motion suggestion**: Push right transition; sequential left-to-right reveal of stages 1 through 5.
- **Images**: `hutech_logo.png` (header).

### Part 3: Live MVP Proof, Business Value & Advantage

#### Slide 08 - 8. Mockup / Demo (Part 1: Scenes 1 & 2)

- **Audience move**: Sees 4 crisp, uncropped live application windows styled with `legacy.html` macOS browser headers proving Scenes 1A–2A work in production.
- **Relationships**: Ordered product walkthrough (`1A Knowledge Graph` → `1B AI JD Studio` → `1C Channel ROI` → `2A CV Hold & 1-Click Magic Link`).
- **Composition**: 2×2 gallery of floating white browser-framed cards (`no-crop` `1.60` screenshots) on pure `#FFFFFF`.
- **Title**: Live MVP Demo (1/2): Graph, JD, ROI & CV Board
- **Core message**: Real-time screenshots from our running 4-container platform for Daehan Precision Vina.
- **Content**:
  - `Scene 1A · Living Knowledge Graph`: Extracted tech stack, ISO 9001 & HR policy nodes
  - `Scene 1B · AI JD Studio`: Grounded job post with automated policy verification
  - `Scene 1C · Channel Attribution`: Pass-rate ROI across LinkedIn, TopCV, Uni & Referrals
  - `Scene 2A · Human-in-Loop CV Board`: HR overrides Marcus (`#A6`) hold via 1-click Magic Link
- **Motion suggestion**: Staggered zoomed entrance of browser frames `1A → 1B → 1C → 2A`.
- **Images**: `hutech_logo.png` (header), `s1_knowledge_graph.png`, `s1_jd_studio.png`, `s1_channel_intel.png`, and `s2_cv_screening_board.png`.

#### Slide 09 - 8. Mockup / Demo (Part 2: Scenes 2B–5)

- **Audience move**: Sees the remaining 4 live browser windows completing Voice AI probing, Hidden Gem calibration, 30-60-90 onboarding, and `SOURCES DISAGREE` policy guardrail.
- **Relationships**: Continuation of the live tour (`2B Voice AI Room` → `3 Hidden Gem Matrix` → `4 30-60-90 Plan` → `5 Policy Copilot`).
- **Composition**: Matching 2×2 floating white browser-framed gallery (`no-crop` `1.60` screenshots) on pure `#FFFFFF`.
- **Title**: Live MVP Demo (2/2): Voice AI, Hidden Gem & Copilot
- **Core message**: End-to-end continuity from spoken technical proof to safe Day-90 employee onboarding.
- **Content**:
  - `Scene 2B · Recorded Voice AI`: Adaptive follow-up probing ISO 9001 change control
  - `Scene 3 · 2×2 Hidden Gem Matrix`: Surfacing `Hannah Park (#A5)` with exact transcript quotes
  - `Scene 4 · 30-60-90 Probation Plan`: 1-click HR approval converts candidate to employee
  - `Scene 5 · Conflict-Aware Copilot`: Cites clauses & alerts `SOURCES DISAGREE`
- **Motion suggestion**: Push right from Demo 1/2; staggered zoomed entrance of browser frames `2B → 3 → 4 → 5`.
- **Images**: `hutech_logo.png` (header), `s2_live_ai_interview.png`, `s3_hidden_gem_evidence.png`, `s4_onboarding_roadmap.png`, and `s5_policy_copilot.png`.

#### Slide 10 - 9. Feasibility & Business Value

- **Audience move**: Evaluates ROI and technical readiness — sees `32.5h → 5.5h (-78%)` effort reduction alongside a live 4-node Docker architecture costing `$0.12` per candidate.
- **Relationships**: Left `roi-dumbbell` chart proves 27h saved per hire; right KPI pills (`-78%`, `3.2×`, `$0.12`) and connected 4-container Docker nodes (`:5174`, `:3001`, `:8001`, `:3307`) prove immediate deployability.
- **Composition**: Airy 2-zone layout on pure `#FFFFFF`: sleek `#F8FAFC`-tinted dumbbell chart on the left paired with 3 minimalist stat pills and 4 connected circular/pill Docker service nodes on the right.
- **Title**: 78% Fewer Admin Hours via a Live Docker MVP
- **Core message**: High-ROI, low-cost (`$0.12/candidate`) modular stack ready for immediate enterprise pilot.
- **Content**:
  - Hours per Hire (`32.5h Manual → 5.5h InterviewPath`): `JD & Policy (6.0h → 0.8h)` · `CV + Screen (14.0h → 2.5h)` · `Round-2 Brief (4.5h → 0.7h)` · `Day-90 & RAG (8.0h → 1.5h)`
  - Hero KPIs: `-78% Admin Hours` · `3.2× Hidden Gems` · `$0.12 AI Cost / Cand.`
  - 4-Container Stack: `:5174 HR Portal (React)` · `:3001 Candidate App (Next.js)` · `:8001 FastAPI AI Core` · `:3307 MySQL 8 Graph DB`
- **Visualization**: `roi-dumbbell` (`chart/dumbbell_chart`) comparing manual vs InterviewPath hours across 4 stages.
- **Native-ready**: `roi-dumbbell=no`
- **Motion suggestion**: Dumbbell chart wipes in from left, followed by staggered zoom on the 3 KPI pills and sequential rise-up of the Docker stack.
- **Images**: `hutech_logo.png` (header).
- **Data class**: scenario

#### Slide 11 - 10. Competitive Advantage

- **Audience move**: Contrasts `Legacy ATS & Point AI` against `InterviewPath`'s green-highlighted `OUR ADVANTAGE` column (`legacy.html` Slide 09 style) and remembers Team Zenith from HUTECH University.
- **Relationships**: Six enterprise capabilities contrasted across `Legacy Keyword ATS`, `Point AI Tools`, and `InterviewPath (OUR ADVANTAGE)`, anchored by Team Zenith's closing banner.
- **Closing impact**: Binding takeaway — `"Not Just Screening — The AI Talent Memory Layer for the Entire Hiring & Onboarding Journey — Team Zenith (HUTECH University)"`; Reference composition — airy `legacy.html` `VS` comparison matrix highlighting `InterviewPath` in soft `#F0FDF4` with a floating green `OUR ADVANTAGE` pill badge above a sleek Team Zenith closing bar.
- **Title**: Why InterviewPath Wins
- **Core message**: Not just CV screening — a white-box Talent Memory layer from handbook to Day-90 employee.
- **Content**:
  - Feature Matrix (`Legacy ATS` vs `Point AI Tools` vs `InterviewPath — OUR ADVANTAGE`):
    1. `Graph-Grounded JD Studio`: `✕ Manual Word` · `✕ None` · `✓ Auto JD + Policy Check`
    2. `Channel Quality Attribution`: `⚠ Vanity Clicks` · `✕ None` · `✓ Verified Pass-Rate ROI`
    3. `Spoken Proof ('Hidden Gem' 2×2)`: `✕ Keyword Reject` · `⚠ Generic Score` · `✓ 2×2 Matrix + Quotes`
    4. `Human-in-the-Loop Override`: `✕ Rigid Filter` · `✕ Black-Box` · `✓ 1-Click Magic Link`
    5. `30-60-90 Probation Roadmap`: `✕ Disconnected` · `✕ Ends at Offer` · `✓ Built from Interview Gaps`
    6. `Conflict-Aware Policy Copilot`: `⚠ Static PDFs` · `✕ None` · `✓ Cited + SOURCES DISAGREE`
  - Closing Strip: `Team Zenith · HUTECH University — Lưu Gia Bảo · Tạ Hoàng Thành · Nguyễn Phương Quang`
- **Visualization**: `comp-matrix` (`table/feature_matrix`) contrasting 3 platforms across 6 capabilities with `legacy.html` `OUR ADVANTAGE` highlight styling.
- **Native-ready**: `comp-matrix=no`
- **Motion suggestion**: Comparison matrix reveals cleanly, followed by a subtle emphasis on the closing Team Zenith banner.
- **Images**: `hutech_logo.png` (header).

## X. Speaker Notes Requirements

- **Generation**: disabled
