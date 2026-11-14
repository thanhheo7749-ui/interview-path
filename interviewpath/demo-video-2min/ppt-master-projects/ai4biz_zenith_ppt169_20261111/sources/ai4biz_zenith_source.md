# AI4Biz 2026 — Track 1: Human Resources & Recruitment
## Team Zenith (HUTECH University) — InterviewPath

### 1. Team & Competition Metadata
- **Competition:** AI4Biz 2026
- **Track:** Track 1 — Human Resources & Recruitment (Ứng dụng AI để cải thiện quy trình tuyển dụng và quản trị nhân sự)
- **University:** HUTECH University (Đại học Công nghệ TP.HCM)
- **Team Name:** Zenith (`AI4Biz_Zenith_2026`)
- **Team Members:**
  1. Lưu Gia Bảo
  2. Tạ Hoàng Thành
  3. Nguyễn Phương Quang
- **Product Name:** InterviewPath
- **Tagline:** Evidence-First AI for Recruitment & Onboarding
- **Submission Format:** PDF (from natively editable PPTX), English language, maximum 15 slides, pure white background (`#FFFFFF`) across all slides, low-text & visually abstractable diagrams + AI concept visuals + real MVP UI screenshots.
- **Bonus Criterion:** Working Prototype / MVP (100% built 4-container Docker MVP + 2m30s live demo video).
- **Final Pitch Context:** Max 15 minutes live English presentation by 3 team members + 2-minute demo video + 5-minute Q&A with judges at Cobi Home on 19/11/2026.

### 2. Track 1 Core Requirements Mapped to InterviewPath
1. **AI-assisted CV screening against hiring criteria** (`AI hỗ trợ sàng lọc CV theo tiêu chí tuyển dụng`):
   - **Fit Compass & Adaptive Spoken Probing:** Parses candidate CVs (`.docx`/`.pdf`) against must-have Knowledge Graph nodes, lets HR override paper-CV holds via 1-click Magic Link, conducts a live recorded Voice AI Round 1 interview with dynamic follow-up questions, and plots candidates on a **2x2 Evidence Calibration Matrix** (`Priority`, `Strong CV / Unclear Answers`, `Hidden Gem`, `Not Enough Evidence`).
2. **AI assistant for Job Descriptions & recruitment content** (`Trợ lý AI hỗ trợ tạo mô tả công việc và nội dung tuyển dụng`):
   - **Graph-Grounded AI JD Studio:** Converts a Hiring Manager's structured request + living Company Knowledge Graph nodes (e.g., Spring Boot, Oracle SQL tuning, design docs before coding, ISO 9001 change-control) into a policy-checked, bias-audited Job Description in one click.
3. **AI data analytics to identify effective sourcing channels** (`AI phân tích dữ liệu để xác định kênh thu hút ứng viên hiệu quả`):
   - **Channel Quality Attribution Analytics:** Connects sourcing channels (`LinkedIn`, `TopCV`, `University`, `Referrals`, `ITviec`, `Facebook`) directly to downstream Round 1 spoken-evidence pass rates, Hidden Gems discovered, and cost-per-verified-hire rather than vanity click counts.
4. **Internal AI assistant for company policy & process lookup** (`Trợ lý nội bộ giúp nhân viên tra cứu chính sách và quy trình công ty`):
   - **30-60-90 Onboarding & Conflict-Aware Policy Copilot:** Converts Round 1 skill gaps into a personalized 30-60-90 day probation roadmap upon hiring, and provides a citation-backed Multi-Document RAG Copilot that explicitly flags **`SOURCES DISAGREE`** when two internal policy documents (e.g., Korean HQ Handbook vs. Annual & Statutory Leave Policy) contradict each other, preventing AI hallucination until HR resolves the rule.

### 3. Suggested Competition Slide Structure (10 Core Sections -> 11 Visual Slides)
1. **Title:** Team Zenith (HUTECH University), members (Lưu Gia Bảo, Tạ Hoàng Thành, Nguyễn Phương Quang), InterviewPath, tagline, visual hero concept.
2. **Business Problem:** 4 broken links in enterprise hiring & HR operations:
   - `3–5 Days` slow manual copy-paste JDs disconnected from real engineering standards.
   - `42% Waste` blind job-board spend counting clicks instead of verified interview pass rates.
   - `68% Missed` paper CV keyword filters auto-rejecting strong builders who write concise CVs ("Hidden Gems").
   - `45m / Day` HR & new-hire time lost to generic onboarding checklists and contradictory PDF handbooks.
3. **Target Business & Users:** Mid-to-large Tech, SaaS, FinTech & Precision Manufacturing enterprises (100–2,000+ employees, e.g., Daehan Precision Vina scaling 20–200 engineering roles/year) connecting 4 roles around 1 hub:
   - **HR & Talent Team:** Pain = 200+ CVs & manual JDs -> Gain = 1-Click JD & Evidence Board.
   - **Job Candidates (Marcus Vance, Hannah Park):** Pain = Black-box CV rejection -> Gain = Fit Compass & 24/7 Voice AI Room.
   - **Hiring Managers:** Pain = Unverified Round 2 interviews -> Gain = Citation-Backed Round 2 Briefs.
   - **Probation New Hires (Day 1–90):** Pain = Conflicting rulebooks -> Gain = 30-60-90 Roadmap & Cited RAG Copilot.
4. **Business Insight:** *"Paper CVs Are Claims. Spoken Answers Are Proof."*
   - **2x2 Evidence Calibration Matrix** (`Paper CV Fit` vs. `Spoken Interview Proof`) unlocks the **Hidden Gem** quadrant (`Hannah Park #A5`: concise CV missed by ATS, but strong spoken Java, Spring Boot & ISO 9001 change-control proof).
   - Continuous memory loop: Interview evidence doesn't vanish after hiring — it powers Day 1–90 onboarding, while Conflict-Aware RAG eliminates silent policy contradictions.
5. **Proposed Solution:** Closed-loop 5-stage AI Talent Memory Pipeline (from Company Handbooks -> AI JD -> Channel ROI -> Voice AI Screen -> Day-90 Onboarding & Policy Copilot).
6. **How AI Helps:** 4 specialized AI engines directly answering all 4 Track 1 bullets (`Input -> AI Engine -> Verified Output`).
7. **How It Works:** End-to-end visual data flow across the 5 live demo scenes (`Scene 1` to `Scene 5`).
8. **Live MVP Demo (Part 1 — Scenes 1 & 2):** Real screenshots from our running application:
   - Living Knowledge Graph (`Daehan Precision Vina` engineering & HR rules) + AI JD Studio + Channel Attribution.
   - CV Hold override (`Marcus Vance #A6`) + 1-click Magic Link + Live Recorded Voice AI Interview Room with adaptive ISO 9001 follow-up question.
9. **Live MVP Demo (Part 2 — Scenes 3, 4 & 5):** Real screenshots from our running application:
   - 2x2 Evidence Matrix surfacing **Hidden Gem `Hannah Park (#A5)`** + Citation-backed Round 2 Brief.
   - 1-click **30-60-90 Day Probation Plan** approval converting candidate into active employee.
   - **Internal Policy Copilot** answering annual leave query with exact citations + **`SOURCES DISAGREE`** conflict alert.
10. **Feasibility & Business Value:**
    - **Production-Ready 4-Container Docker MVP:** `:5174` HR Portal (React/Vite), `:3001` Candidate & Employee App (Next.js), `:8001` FastAPI + Multi-Doc RAG + Voice Prober, `:3307` MySQL 8 Knowledge Graph & Evidence Store.
    - **Expected ROI (Scenario Benchmarks per Hire):** Cuts HR & engineering admin time from **32.5h to 5.5h (-78%)**: JD & Policy Check (`6.0h -> 0.8h`), CV + Round 1 Screen (`14.0h -> 2.5h`), Round 2 Brief (`4.5h -> 0.7h`), Onboarding & Policy Q&A (`8.0h -> 1.5h`); **3.2x** Hidden Gems surfaced; **~$0.12** AI inference cost per screened candidate.
11. **Competitive Advantage & Closing:** Comparison matrix (`Legacy Keyword ATS` vs. `Point AI Interview Tools` vs. `InterviewPath Unified White-Box Platform`) across 6 capabilities (Graph-Grounded JD, Channel Pass-Rate ROI, 2x2 Hidden Gem Matrix, Human-in-the-Loop Override, Auto 30-60-90 Plan, Conflict-Aware RAG Copilot) + Closing takeaway for **Team Zenith (HUTECH University)**.
