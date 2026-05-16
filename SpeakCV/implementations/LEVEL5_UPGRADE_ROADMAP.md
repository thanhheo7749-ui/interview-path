# SpeakCV Level 5 Upgrade Roadmap

## 1. Mục tiêu của roadmap này
Roadmap này không chỉ liệt kê các hạng mục kỹ thuật cần làm, mà còn nhằm biến SpeakCV thành một sản phẩm **có thể claim Level 5 một cách thuyết phục** trong demo/pitch.

Mục tiêu ở đây không phải là cố build một hệ thống AI quá lớn trong thời gian ngắn, mà là:
1. tạo ra một **kiến trúc Level 5 đủ rõ**,
2. build **2 proof points hybrid AI chạy thật**,
3. làm cho audience có thể **nhìn thấy ngay** sự khác biệt giữa SpeakCV và một app chỉ gọi LLM API.

Roadmap này vì vậy ưu tiên mạnh vào:
- visible proof
- explainability
- structured signals
- orchestration rõ ràng
- presentation-ready output

---

## 2. North-star direction
SpeakCV nên được phát triển và trình bày như:

> A hybrid AI decision-support system for interview preparation and CV evaluation.

Điều này có nghĩa là:
- LLM vẫn rất quan trọng
- nhưng LLM không được là nơi duy nhất quyết định đầu ra
- hệ thống phải có thêm specialist scoring layers
- output phải có evidence, sub-scores, hoặc quality indicators đủ rõ

Roadmap không theo hướng “thêm AI cho có”, mà theo hướng:
- biến các workflow hiện tại thành **hybrid workflows có thể defend được**
- để khi demo, người xem thấy rõ đây là một hệ thống có cấu trúc

---

## 3. Trọng tâm chiến lược: Dual-Proof Level 5
Roadmap này xoay quanh hai bằng chứng phải build thật.

## 3.1 Proof Point A — Interview Intelligence
### Điều cần chứng minh
SpeakCV không chỉ hiểu **what the user says**, mà còn đánh giá được **how the user says it**.

### Kết quả người xem phải thấy được
1. transcript confidence
2. speaking quality signals
3. phản hồi hoặc coaching thay đổi theo tín hiệu đó

### Tác động chiến lược
Proof point này giúp SpeakCV thoát khỏi hình ảnh “voice chatbot” và tiến gần hơn tới một interview coach có specialist AI layers.

## 3.2 Proof Point B — CV Reasoning Intelligence
### Điều cần chứng minh
SpeakCV không chỉ keyword match CV với JD, mà có một reasoning/scoring layer đủ rõ để đánh giá mức độ phù hợp và độ tin cậy của CV.

### Kết quả người xem phải thấy được
1. graph-informed score hoặc structured skill score
2. missing prerequisite skills
3. inflation-risk signal hoặc summary
4. final explanation sinh ra từ các signals trên

### Tác động chiến lược
Proof point này giúp SpeakCV thoát khỏi hình ảnh “CV checker dùng LLM” và trở thành một decision-support engine đáng tin hơn.

---

## 4. Kiến trúc đích
Kiến trúc cần tiến hóa từ:

`Route -> Prompt -> LLM -> UI`

to:

`Route -> Orchestrator -> Specialist Scoring / Retrieval -> LLM Explainer -> Evidence + Metrics -> UI`

## 4.1 Vai trò từng lớp
1. **Route layer**
   - giữ API ổn định
   - nhận request từ frontend

2. **Orchestrator layer**
   - quyết định pipeline nào chạy
   - gom signals từ các specialist modules
   - quản lý fallback
   - tạo response cuối cùng có cấu trúc

3. **Specialist scoring layer**
   - transcript quality
   - prosody scoring
   - skill graph scoring
   - inflation-risk scoring

4. **LLM explainer layer**
   - biến các signals có cấu trúc thành giải thích tự nhiên
   - không nên là nơi duy nhất quyết định result

5. **Evidence and metrics layer**
   - expose score blocks
   - attach evidence
   - ghi latency / fallback / step success

### Tại sao kiến trúc này là bắt buộc
Nếu không có lớp orchestrator và specialist signals, mọi nâng cấp sau cùng vẫn sẽ bị nhìn như prompt engineering nâng cao. Kiến trúc mới chính là thứ biến câu chuyện Level 5 từ “ý tưởng” thành “hệ thống”.

---

## 5. Lộ trình triển khai theo giai đoạn

## Phase 0 — Chuẩn hóa nền tảng để hỗ trợ claim Level 5
**Mục tiêu:** tạo xương sống kỹ thuật để 2 proof points có chỗ gắn vào.

### Việc cần làm
1. Tạo `orchestrator` cho interview và CV flows.
2. Chuẩn hóa response schema:
   - `content`
   - `analysis`
   - `evidence`
   - `usage`
   - `trace_id`
3. Tách logging AI thành event chuẩn.
4. Định nghĩa nơi chứa specialist outputs.

### Definition of done
- Router không còn ôm toàn bộ logic AI
- Response shape đủ chỗ để hiển thị signals trong UI
- Có cấu trúc đủ rõ để kể kiến trúc trên slide

### Vì sao phase này quan trọng
Không có phase này thì các proof points sau dễ bị gắn chắp vá, khiến demo vẫn trông như nhiều prompt được chồng lên nhau.

---

## Phase 1 — Build Proof Point A: Interview Intelligence
**Mục tiêu:** tạo ra một bằng chứng Level 5 nhìn thấy được ngay trong luồng interview.

### 1.1 Thành phần cần build
1. **Transcript quality scoring**
   - input: transcript, lang, audio metadata
   - output: confidence score, low-quality flags, needs_confirmation

2. **Transcript confirmation flow**
   - nếu confidence thấp, cho user sửa transcript trước khi tiếp tục

3. **Prosody scoring**
   - pace
   - pause ratio
   - filler density
   - confidence proxy

4. **Adaptive coaching response**
   - dùng signals trên để điều chỉnh coaching hoặc phản hồi

### 1.2 UI output nên có
- transcript confidence card
- speaking quality cards
- visible “AI noticed this signal” behavior

### 1.3 Giá trị pitch
Bạn có thể nói:
> Our interview AI does not only analyze content. It also checks speaking quality and uses those signals to guide coaching behavior.

### Definition of done
- Có transcript confidence chạy thật
- Có ít nhất một speaking-signal block chạy thật
- Có hành vi phản hồi thay đổi theo signals
- Audience có thể hiểu proof point này trong vài giây

---

## Phase 2 — Build Proof Point B: CV Reasoning Intelligence
**Mục tiêu:** tạo ra bằng chứng Level 5 thứ hai trong luồng CV.

### 2.1 Thành phần cần build
1. **Skill graph scoring**
   - score theo prerequisite relationships
   - không chỉ keyword overlap

2. **Inflation-risk detection**
   - phát hiện mismatch giữa role claim, years, scope, tools, evidence density

3. **Evidence block**
   - matched skills
   - missing prerequisites
   - inflation signals

4. **Explanation layer**
   - dùng LLM để giải thích từ structured signals

### 2.2 UI output nên có
- graph-informed score
- missing skill / prerequisite list
- inflation-risk label hoặc summary
- explanation gắn với signals

### 2.3 Giá trị pitch
Bạn có thể nói:
> Our CV engine does not only match keywords. It reasons over skill dependencies and signals possible overstatement risk before producing the final explanation.

### Definition of done
- Có ít nhất một graph-based score chạy thật
- Có inflation-risk summary chạy thật
- Có evidence block đủ rõ trên UI hoặc response
- Người xem nhìn ra khác biệt so với ATS checker thông thường

---

## Phase 3 — Explainability and presentation layer
**Mục tiêu:** biến 2 proof points thành thứ dễ nhìn, dễ hiểu, dễ thuyết phục trên sân khấu.

### Việc cần làm
1. Tạo signal cards hoặc score blocks cho interview flow.
2. Tạo evidence block cho CV flow.
3. Tách `raw signal` khỏi `natural-language explanation`.
4. Chuẩn hóa wording để output nghe chuyên nghiệp, không gimmicky.

### Vì sao phase này quan trọng
Nhiều hệ thống có kỹ thuật tốt nhưng demo không thuyết phục vì audience không “thấy” được AI layer. Phase này biến kỹ thuật thành thứ có thể kể được.

### Definition of done
- Có UI hoặc output format giúp audience hiểu proof points ngay
- Mỗi proof point có thể giải thích bằng 1-2 câu rất ngắn

---

## Phase 4 — Lightweight evaluation and credibility layer
**Mục tiêu:** có vài con số và operational signals để hệ thống trông đáng tin hơn.

### Việc cần làm
1. Log:
   - latency
   - fallback rate
   - step success/failure
   - score visibility
2. Chuẩn bị một bộ demo-grade test cases:
   - interview: audio tốt / audio xấu / trả lời run / trả lời tự tin
   - CV: CV tốt / CV thiếu prerequisite / CV có tín hiệu overclaim
3. Nếu kịp, làm admin/demo metrics view đơn giản.

### Vì sao phase này quan trọng
Khách mời thực dụng thường bị thuyết phục mạnh hơn khi bạn có thể nói:
- hệ thống fallback ra sao
- tại sao score này xuất hiện
- latency có được kiểm soát không

### Definition of done
- Có ít nhất vài metric có thể nhắc trong pitch
- Có test cases rõ để diễn demo an toàn hơn

---

## Phase 5 — Optional Korean-compatible enhancements
**Mục tiêu:** tăng mức phù hợp với audience người Hàn mà không biến dự án thành “Korea gimmick”.

### Nên thêm nếu còn thời gian
1. professionalism presets cho interview tone
2. formal / supportive / direct response modes
3. curated workplace communication snippets
4. future-ready section cho company-specific culture knowledge

### Không nên làm
1. claim hiểu sâu văn hóa Hàn khi chưa build thật
2. biến Korean-specificity thành trọng tâm lớn hơn core AI proof
3. nhồi quá nhiều yếu tố local nếu không phục vụ demo value

### Cách dùng đúng
Korean compatibility nên đóng vai trò:
- trust layer
- polish layer
- presentation-quality layer

chứ không nên là trụ cột duy nhất của câu chuyện sản phẩm.

---

## 6. Thứ tự ưu tiên thực tế

### Ưu tiên 1 — Bắt buộc phải có
1. orchestrator layer
2. interview proof point
3. CV proof point

### Ưu tiên 2 — Làm cho proof points nhìn thấy được
1. signal cards
2. evidence block
3. structured response shape

### Ưu tiên 3 — Tăng độ tin cậy
1. fallback visibility
2. latency logging
3. demo-grade metrics

### Ưu tiên 4 — Tăng độ phù hợp với audience
1. polished wording
2. professional interaction style
3. optional Korean-compatible additions

---

## 7. Cách kể roadmap này trong buổi pitch
Roadmap không nên được kể theo kiểu:
- chúng tôi sẽ thêm rất nhiều AI module
- chúng tôi sẽ build một hệ multi-agent lớn

Roadmap nên được kể theo kiểu:
1. **Today:** SpeakCV already supports interview and CV workflows.
2. **Next:** we are transforming both into hybrid AI workflows with visible specialist scoring.
3. **Proof:** we show two working Level 5 proof points, not just architecture slides.
4. **Scale path:** from these proof points, we can grow toward deeper grounding, evaluation, and richer orchestration.

Cách kể này giúp audience tin rằng:
- sản phẩm không viển vông
- roadmap không quá rộng
- đội ngũ hiểu rõ thứ gì cần build trước

---

## 8. Kết luận cuối
Roadmap tốt nhất cho SpeakCV không phải là cố gắng build toàn bộ giấc mơ Level 5 ngay lập tức.

Roadmap tốt nhất là:
1. **xây kiến trúc đủ rõ**
2. **build 2 proof points hybrid AI chạy thật**
3. **làm cho chúng nhìn thấy được trong demo**
4. **dùng chúng để justify claim Level 5-capable system**

Nếu làm đúng theo hướng này, SpeakCV sẽ:
- thoát khỏi framing “LLM wrapper”
- có 2 bằng chứng kỹ thuật rất dễ kể
- phù hợp với audience thực dụng
- và có một câu chuyện Level 5 vừa mạnh vừa trung thực

Nói ngắn gọn:
- **đừng cố build mọi thứ**
- **hãy build đúng 2 bằng chứng nhìn thấy được**
- rồi dùng chúng để biến toàn bộ sản phẩm thành một câu chuyện Level 5 có sức nặng
