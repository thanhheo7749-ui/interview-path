# Kịch bản Video Demo 2 Phút 30 Giây — Human Resources & Recruitment

> [!IMPORTANT]
> **Thông số kỹ thuật video:**
> - **Thời lượng mục tiêu:** ~2 phút 30 giây (`150s`, gồm Intro 2.4s + 5 Phân cảnh thực tế + Outro 2.6s)
> - **Giọng đọc (Voiceover):** Nam Tiếng Anh (`Kokoro am_adam`, tốc độ `0.8`) + Phụ đề Tiếng Anh tự động (`pill` style)
> - **Dữ liệu & Giao diện:** Công ty mẫu **Daehan Precision Vina** (`hr@daehan-precision.sample` / `DemoPass123!`), giao diện **English**
> - **Trình tự luồng:** Theo đúng vòng đời tuyển dụng thực tế bạn đã chọn: **1. Tạo JD bằng AI $\rightarrow$ 2. Sàng lọc CV (Cổng 3001 + Cổng 5174) $\rightarrow$ 3. Phân tích kênh tuyển dụng $\rightarrow$ 4. Trợ lý nội bộ tra cứu chính sách**

---

## Tổng quan Hình chụp Màn hình Thực tế (8 Cảnh quay)

````carousel
![Phân cảnh 1A — Tạo yêu cầu tuyển dụng tại /hiring-requests](/home/vanii/.gemini/antigravity-cli/brain/2496d9cb-46a1-4236-9ab0-47c7b584532d/scene1_hiring_requests.png)
<!-- slide -->
![Phân cảnh 1B — Trợ lý AI tạo Mô tả công việc trong JD Studio](/home/vanii/.gemini/antigravity-cli/brain/2496d9cb-46a1-4236-9ab0-47c7b584532d/scene1_jd_studio.png)
<!-- slide -->
![Phân cảnh 2A — Ứng viên nộp CV trực tiếp trên cổng 3001](/home/vanii/.gemini/antigravity-cli/brain/2496d9cb-46a1-4236-9ab0-47c7b584532d/scene2a_candidate_apply.png)
<!-- slide -->
![Phân cảnh 2A — Fit Compass đối chiếu CV theo từng tiêu chí tuyển dụng](/home/vanii/.gemini/antigravity-cli/brain/2496d9cb-46a1-4236-9ab0-47c7b584532d/scene2a_fit_compass.png)
<!-- slide -->
![Phân cảnh 2B — Bảng sàng lọc Evidence Board trên cổng HR 5174](/home/vanii/.gemini/antigravity-cli/brain/2496d9cb-46a1-4236-9ab0-47c7b584532d/scene2b_evidence_board.png)
<!-- slide -->
![Phân cảnh 2B — Chi tiết bằng chứng từng tiêu chí của ứng viên Hidden Gem & Nút duyệt](/home/vanii/.gemini/antigravity-cli/brain/2496d9cb-46a1-4236-9ab0-47c7b584532d/scene2b_hidden_gem_detail.png)
<!-- slide -->
![Phân cảnh 3 — AI phân tích hiệu quả các kênh tuyển dụng (Channel Intelligence)](/home/vanii/.gemini/antigravity-cli/brain/2496d9cb-46a1-4236-9ab0-47c7b584532d/scene3_channel_intelligence.png)
<!-- slide -->
![Phân cảnh 4 — Trợ lý nội bộ Copilot trả lời chính sách nghỉ phép & cảnh báo xung đột tài liệu](/home/vanii/.gemini/antigravity-cli/brain/2496d9cb-46a1-4236-9ab0-47c7b584532d/scene4_copilot_policy.png)
````

---

## Chi tiết Kịch bản Từng Phân cảnh (Timeline 2m30s)

### 🎬 Intro Card (`0:00 – 0:02.4`)
- **Tiêu đề:** `InterviewPath`
- **Phụ đề:** `AI-Powered Human Resources & Recruitment`

---

### 1️⃣ Scene 1 (`0:02 – 0:31`, ~29s): Trợ lý AI hỗ trợ tạo mô tả công việc và nội dung tuyển dụng
* **Cổng URL:** `http://localhost:5174/login` $\rightarrow$ `http://localhost:5174/hiring-requests` $\rightarrow$ `http://localhost:5174/jd-studio/:draftId`
* **Thao tác tự động trên màn hình:**
  1. HR (`hr@daehan-precision.sample`) đăng nhập vào cổng `http://localhost:5174/login`.
  2. Mở menu **Hiring requests**, điền vị trí `Senior Backend Engineer`, chọn Hiring Manager `Sample Manager`, phòng ban `Backend` $\rightarrow$ bấm **Create request**.
  3. Bấm **Generate draft** để mở **JD Studio**.
  4. Highlight danh sách tiêu chí tuyển dụng do AI rút trích từ chuẩn công ty (`[data-testid="jd-lines"]`), chuyển qua các tab ngôn ngữ (`Tiếng Việt`, `한국어`, `English`), và highlight bảng **Assistant & Checks** (`[data-testid="lint-panel"]`).
* **Lời thoại Tiếng Anh (English Voiceover):**
  > *"Every great hire starts with a clear job description. When a new role opens at Daehan Precision, HR doesn't start from a blank page. She opens Hiring Requests, assigns the role to the Backend team, and clicks Generate Draft. In seconds, InterviewPath's JD Studio pulls verified standards straight from the company knowledge base to write a complete job description in English, Vietnamese, and Korean — complete with must-have criteria, an AI editing assistant, and automatic policy checks."*
* *(Tạm dịch nghĩa Tiếng Việt):*
  > *"Mỗi đợt tuyển dụng thành công đều bắt đầu từ một bản mô tả công việc rõ ràng. Khi mở vị trí mới tại Daehan Precision, HR không cần viết từ trang giấy trắng. Cô mở mục Yêu cầu tuyển dụng, gán cho nhóm Backend và bấm Tạo bản nháp. Chỉ trong vài giây, JD Studio tự động lấy các tiêu chuẩn đã xác thực từ kho tri thức công ty để viết bản mô tả công việc hoàn chỉnh bằng tiếng Anh, tiếng Việt và tiếng Hàn — kèm các tiêu chí bắt buộc, trợ lý chỉnh sửa AI và bộ kiểm duyệt tự động."*

---

### 2️⃣ Scene 2A (`0:31 – 1:02`, ~31s): AI hỗ trợ sàng lọc CV theo tiêu chí — Góc nhìn Ứng viên & Fit Compass
* **Cổng URL:** `http://localhost:3001/jobs/daehan-precision-backend-developer-007dff` $\rightarrow$ `http://localhost:3001/applications`
* **Thao tác tự động trên màn hình:**
  1. Mở trang tuyển dụng công khai `http://localhost:3001/jobs/daehan-precision-backend-developer-007dff` (vị trí *Backend Developer*).
  2. Bấm **Apply**, nhập tên `Tran Thi B`, email `tran.thib.demo@example.com`, đính kèm file CV `Tran_Thi_B_Backend_CV.docx` và bấm **Send my application**.
  3. Chuyển sang `http://localhost:3001/applications`, bấm **See how you fit** để mở màn hình **Fit Compass**.
  4. Highlight bảng đối chiếu từng tiêu chí tuyển dụng (`Matches` / `Not seen in your CV`), cuộn xuống bấm **Continue to the interview** tới màn hình kiểm tra micro phòng phỏng vấn AI.
* **Lời thoại Tiếng Anh (English Voiceover):**
  > *"Once the role is live, candidates apply directly on the candidate portal. Tran Thi B uploads her resume for the Backend Developer role — no pre-registration required. Right away, InterviewPath's AI screens her CV against every job requirement and displays her Fit Compass, showing line by line which criteria her resume already matches and what will be explored next. Instead of waiting days for a manual review, qualified candidates are invited straight into a spoken AI screening interview."*
* *(Tạm dịch nghĩa Tiếng Việt):*
  > *"Khi tin tuyển dụng được đăng, ứng viên nộp hồ sơ trực tiếp trên cổng ứng viên. Tran Thi B tải CV ứng tuyển vị trí Backend Developer mà không cần tạo tài khoản trước. Ngay lập tức, AI của InterviewPath sàng lọc CV của cô theo từng yêu cầu công việc và hiển thị bảng Fit Compass, chỉ rõ từng dòng tiêu chí nào đã khớp trên CV và tiêu chí nào sẽ được hỏi thêm. Thay vì phải chờ đợi nhiều ngày, ứng viên phù hợp được mời vào thẳng phòng phỏng vấn giọng nói với AI."*

---

### 3️⃣ Scene 2B (`1:02 – 1:31`, ~29s): AI hỗ trợ sàng lọc CV theo tiêu chí — Góc nhìn HR Evidence Board & Hidden Gem
* **Cổng URL:** `http://localhost:5174/jobs` $\rightarrow$ `http://localhost:5174/jobs/4/board`
* **Thao tác tự động trên màn hình:**
  1. Quay lại cổng HR `http://localhost:5174/jobs`, bấm **Open board** để vào bảng sàng lọc **Candidate Board** (`/jobs/4/board`).
  2. Highlight ô **Priority** và ô **Hidden Gem** (`[data-testid="cell-hidden_gem"]`).
  3. Bấm vào ứng viên **Pham Thi Lan** trong ô **Hidden Gem** để mở bảng chi tiết bên phải (`[data-testid="detail-panel"]`).
  4. Cuộn qua bảng chấm điểm từng tiêu chí (`Must-have: met — Evidence found`), highlight mục **AI suggestion, for your review**, rồi bấm nút **Approve** (`[data-testid="decision-bar"]`).
* **Lời thoại Tiếng Anh (English Voiceover):**
  > *"Back on the HR portal, every applicant is organized on the Evidence Board. Rather than rejecting resumes with rigid keyword filters, InterviewPath combines CV screening with spoken interview evidence. Look at the Hidden Gem lane: Pham Thi Lan's paper resume looked thin, so a traditional ATS would have filtered her out. Yet her spoken answers proved strong Java, Spring Boot, and ISO quality experience. HR reviews the exact requirement evidence and approves her in one click."*
* *(Tạm dịch nghĩa Tiếng Việt):*
  > *"Quay lại cổng HR, toàn bộ ứng viên được sắp xếp trên bảng Evidence Board. Thay vì loại bỏ hồ sơ bằng bộ lọc từ khóa cứng nhắc, InterviewPath kết hợp sàng lọc CV với bằng chứng từ bài phỏng vấn nói. Hãy nhìn vào ô Hidden Gem: CV giấy của Pham Thi Lan khá sơ sài nên các hệ thống lọc truyền thống sẽ đánh trượt. Nhưng câu trả lời phỏng vấn của cô chứng minh kinh nghiệm vững vàng về Java, Spring Boot và quy trình chất lượng ISO. HR kiểm tra bằng chứng theo từng tiêu chí và bấm Duyệt chỉ với một cú nhấp chuột."*

---

### 4️⃣ Scene 3 (`1:31 – 2:00`, ~29s): AI phân tích dữ liệu để xác định kênh thu hút ứng viên hiệu quả
* **Cổng URL:** `http://localhost:5174/jobs` $\rightarrow$ `http://localhost:5174/jobs/4/channels`
* **Thao tác tự động trên màn hình:**
  1. Từ menu **Jobs**, bấm vào **Channels** (`/jobs/4/channels`) để mở trang **Channel Intelligence**.
  2. Bấm nút **Simulated data** để nạp dữ liệu phân tích kênh tuyển dụng.
  3. Highlight bảng thống kê (`[data-testid="channel-table"]`) và di chuột lần lượt qua các dòng `linkedin`, `topcv`, `university`, `facebook`, `referral` để làm nổi bật cột **Applications**, **HR Approved**, **Approval Rate**, **Hidden Gems**, và **Cost (VND)**.
* **Lời thoại Tiếng Anh (English Voiceover):**
  > *"Next, how does HR know where to invest the recruitment budget? InterviewPath's Channel Intelligence tracks every application from source to final decision across LinkedIn, TopCV, university fairs, Facebook, and referrals. Instead of measuring success by raw CV volume, the AI highlights which channels actually deliver HR-approved candidates and hidden gems at the lowest cost per hire — turning recruitment spending into a data-driven decision."*
* *(Tạm dịch nghĩa Tiếng Việt):*
  > *"Tiếp theo, làm sao HR biết nên đầu tư ngân sách tuyển dụng vào đâu? Tính năng Channel Intelligence theo dõi mọi hồ sơ từ nguồn ban đầu đến quyết định cuối cùng qua LinkedIn, TopCV, ngày hội việc làm đại học, Facebook và giới thiệu nội bộ. Thay vì đo lường bằng số lượng CV thô, AI chỉ rõ kênh nào thực sự mang lại nhiều ứng viên được duyệt và nhiều Hidden Gem nhất với chi phí tuyển dụng thấp nhất."*

---

### 5️⃣ Scene 4 (`2:00 – 2:28`, ~28s): Trợ lý nội bộ giúp nhân viên tra cứu chính sách và quy trình công ty
* **Cổng URL:** `http://localhost:5174/copilot` $\rightarrow$ `http://localhost:5174/conflicts`
* **Thao tác tự động trên màn hình:**
  1. Bấm vào menu **Copilot** (`http://localhost:5174/copilot`).
  2. Nhập câu hỏi vào ô `#copilot-question`: `"How many annual leave days do I get, and how do I request leave?"` rồi bấm **Ask**.
  3. Khi câu trả lời hiện ra, highlight nhãn **`SOURCES DISAGREE`** và danh sách tài liệu gốc được trích dẫn (`사내 핸드북` và `Quy định nghỉ phép`).
  4. Bấm sang mục **Conflicts** (`http://localhost:5174/conflicts`) trên thanh menu trái để hiển thị màn hình đối chiếu trực tiếp 2 nguồn tài liệu mâu thuẫn (`Source A` vs `Source B`) cho HR xử lý.
* **Lời thoại Tiếng Anh (English Voiceover):**
  > *"Finally, once new hires join the team, our internal AI Copilot helps employees look up company policies and procedures anytime. When an employee asks about annual leave and how to request time off, Copilot searches the official company handbook and cites the exact source documents. Even better, if two internal policy files contradict each other, it flags 'Sources Disagree' instead of guessing, and routes the conflict straight to HR to resolve."*
* *(Tạm dịch nghĩa Tiếng Việt):*
  > *"Cuối cùng, khi nhân sự mới gia nhập đội ngũ, Trợ lý AI Copilot nội bộ giúp nhân viên tra cứu chính sách và quy trình công ty bất cứ lúc nào. Khi nhân viên hỏi về số ngày phép năm và quy trình xin nghỉ, Copilot tra cứu sổ tay công ty chính thức và trích dẫn chính xác tài liệu nguồn. Hơn thế nữa, nếu hai văn bản nội bộ mâu thuẫn nhau, AI sẽ cảnh báo 'Sources Disagree' thay vì đoán mò, đồng thời chuyển xung đột đó tới mục Conflicts để HR xử lý."*

---

### 🎬 Outro Card (`2:28 – 2:30.6`)
- **Tiêu đề:** `InterviewPath`
- **Phụ đề:** `Smart Screening · AI Job Studio · Channel Analytics · Policy Copilot`
