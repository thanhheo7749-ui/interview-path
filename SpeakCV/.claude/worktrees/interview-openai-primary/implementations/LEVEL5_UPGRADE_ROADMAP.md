# SpeakCV Level 5 Upgrade Roadmap

## 1. Mục tiêu roadmap
Roadmap này biến các gap trong [LEVEL5_GAP_ANALYSIS.md](./LEVEL5_GAP_ANALYSIS.md) thành kế hoạch nâng cấp thực tế để SpeakCV tiến gần Level 5 trong [ideamvp.md](../ideamvp.md).

Mục tiêu không phải thêm AI cho có, mà là xây dựng một **core AI engine** có thể:
- explain được
- ground được
- đo được
- fallback được
- và khác biệt với app chỉ gọi LLM API

---

## 2. North-star architecture

## 2.1 Đích kiến trúc
Cho cả Interview Coach và CV Matcher, kiến trúc đích nên là:

`Client -> API Route -> AI Orchestrator -> Specialist Services -> LLM Explainer -> Response + Evidence + Metrics`

### Specialist services cần có
1. **Transcript Quality Service**
   - chấm chất lượng transcript
   - quyết định có cần confirm lại không

2. **Prosody Service**
   - pace, pause ratio, filler density, confidence proxy

3. **Skill Graph Service**
   - tính match không chỉ theo keyword mà theo prerequisite path

4. **Inflation Classifier**
   - phát hiện tín hiệu CV overclaim / phóng đại

5. **Retrieval Service**
   - lấy evidence từ JD corpus, recruiter rubric, Korean business knowledge, company docs

6. **Critic / Verifier Service**
   - kiểm tra output trước khi trả về

### Vai trò của LLM trong kiến trúc mới
LLM không còn là nơi gánh toàn bộ logic. LLM nên làm 3 việc chính:
1. extract có cấu trúc
2. explain kết quả
3. generate output thân thiện với user

---

## 3. Lộ trình triển khai theo giai đoạn

## Phase 0 - Chuẩn hóa nền tảng hiện tại
**Mục tiêu:** dọn đường để hybrid hóa mà không phá UX hiện có.

### Việc cần làm
1. Tạo `orchestrator` riêng cho interview và CV routes.
2. Chuẩn hóa AI response schema:
   - `content`
   - `analysis`
   - `evidence`
   - `usage`
   - `trace_id`
3. Tách logging AI thành event chuẩn.
4. Đo latency và fallback rate hiện tại để có baseline.

### Kết quả mong muốn
- Có “xương sống” để thêm nhiều model/service mà không nhét hết vào router.

### Vì sao ưu tiên
- Nếu không làm bước này, mọi nâng cấp sau sẽ chỉ làm code phức tạp hơn chứ không tạo ra kiến trúc Level 5 thật.

---

## Phase 1 - Từ prompt app thành grounded system
**Mục tiêu:** đưa SpeakCV từ Level 2/3 lên Level 3 rõ ràng.

### 1.1 Xây RAG / grounding layer
#### Nguồn dữ liệu nên có
- Job descriptions đã chuẩn hóa
- recruiter scoring rubrics
- taxonomy kỹ năng
- Korean work-culture handbook
- company-specific onboarding/interview notes nếu có

### 1.2 Cần bổ sung kỹ thuật
- vector store hoặc retrieval index
- chunking + metadata
- citation object trong response
- retrieval logs

### 1.3 Ứng dụng vào từng flow
#### CV Matcher
- retrieve skill taxonomy, prerequisite concepts, recruiter rubric
- trả lại missing skills + evidence spans

#### Interview Coach
- retrieve role rubric, question bank, Korean interview etiquette snippets
- dùng grounding để chọn câu hỏi và feedback

### Definition of done
- Output có `evidence[]`
- UI hiển thị nguồn giải thích
- Demo được “AI nói gì cũng chỉ ra là dựa vào đâu”

---

## Phase 2 - Thêm specialized models có tác dụng thật
**Mục tiêu:** bắt đầu đạt dấu hiệu Level 5.

## 2.1 Interview Coach hybrid
### Model/service 1: Transcript Quality
- Input: transcript, lang, audio metadata
- Output:
  - confidence score
  - low-quality flags
  - needs_confirmation

### Model/service 2: Prosody Scoring
- Output:
  - pace_wpm
  - pause_ratio
  - filler_rate
  - confidence_score

### Giá trị demo
- Không chỉ nghe nội dung, mà còn chấm cách nói.
- Đây là yếu tố rất thuyết phục cho interview coach.

## 2.2 CV Matcher hybrid
### Model/service 1: Skill Graph Scorer
- dùng graph/taxonomy để score prerequisite-aware
- ví dụ candidate có FastAPI nhưng thiếu System Design thì score không thể bị inflate quá mức

### Model/service 2: CV Inflation Classifier
- phát hiện mô tả quá senior, mismatch giữa years/scope/tools
- output tín hiệu giải thích được

### Giá trị demo
- Đây là phần chuyển SpeakCV từ “ATS keyword checker” sang “AI reasoning layer có structure”.

### Definition of done
- Có ít nhất 2 specialist services nằm trong pipeline chính
- Output hiển thị score thành phần, không chỉ final prose

---

## Phase 3 - Agentic workflow thật sự
**Mục tiêu:** vượt khỏi dynamic prompting, tiến tới Level 4+ rõ ràng.

## 3.1 CV Matcher multi-stage
Pipeline đề xuất:
1. **Extractor**: trích skill, project, years, signals từ CV/JD
2. **Matcher**: score semantic + graph
3. **Verifier**: tìm chỗ thiếu bằng chứng hoặc overclaim
4. **Explainer**: sinh giải thích dễ đọc
5. **Critic**: kiểm tra contradiction trước khi trả về

## 3.2 Interview Coach multi-stage
Pipeline đề xuất:
1. **Listener**: lấy transcript + quality
2. **Behavior Analyzer**: intent/confidence/nervousness
3. **Topic Planner**: chọn topic tiếp theo từ graph/rubric
4. **Coach Generator**: sinh câu hỏi/feedback
5. **Reviewer**: kiểm tra policy, language, clarity

## 3.3 Điều cần có để gọi là agentic thật
- step-specific logs
- retry ở từng bước
- decision trace
- verifier/critic stage hoạt động độc lập với generator

### Definition of done
- Có trace của từng bước trong một turn
- Có ít nhất 1 critic/verifier step có thể chặn hoặc sửa output

---

## Phase 4 - Evaluation, benchmark, defendability
**Mục tiêu:** có số liệu để thuyết phục ban giám khảo.

## 4.1 Eval cho CV Matcher
Tạo bộ 100-300 cặp CV/JD có nhãn recruiter:
- suitable / borderline / unsuitable
- matched skills
- missing prerequisites
- inflation risk

### Metric nên báo cáo
- precision@k
- ranking agreement với recruiter
- hallucination rate
- explanation usefulness score

## 4.2 Eval cho Interview Coach
Tạo bộ audio/text eval:
- EN/VI accents khác nhau
- nervous vs confident
- skip vs answer vs reverse question

### Metric nên báo cáo
- transcript capture quality
- confidence detection accuracy
- topic routing correctness
- human rating cho feedback usefulness

## 4.3 Observability dashboard
Cần có:
- provider mix
- latency p50/p95
- fallback rate
- step error rate
- cost/session
- cache hit rate nếu có caching

### Definition of done
- Có bảng before/after so với baseline prompt-only
- Có biểu đồ để đưa thẳng lên slide demo

---

## Phase 5 - Korean-specific differentiation
**Mục tiêu:** biến SpeakCV thành sản phẩm có câu chuyện riêng với doanh nghiệp Hàn.

## 5.1 Dữ liệu cần bổ sung
- Korean business etiquette corpus
- interview etiquette by seniority
- honorific/formality examples
- onboarding communication norms

## 5.2 Khả năng nên thêm
1. formality adaptation
2. Korea-specific feedback for answer tone
3. company-culture-aware guidance
4. explainability có trích nguồn Korean norms

## 5.3 Giá trị sân khấu
Đây là phần làm judge cảm thấy sản phẩm không phải generic AI coach, mà là product hiểu ngữ cảnh target market.

---

## 6. Quick wins nên làm ngay

## Quick win 1 - AI Orchestrator
- tạo layer trung gian giữa router và AI services
- tác động lớn nhất lên kiến trúc

## Quick win 2 - Transcript confirmation
- nếu transcript confidence thấp thì cho user sửa trước khi generate feedback
- vừa tăng chất lượng vừa là demo dễ thấy

## Quick win 3 - Skill graph scoring v1
- chưa cần GNN
- chỉ cần graph-based weighted scoring có explanation

## Quick win 4 - Evidence block cho CV review
- trả matched keywords, missing skills, source span
- tăng explainability ngay cả khi chưa có full RAG

## Quick win 5 - AI metrics admin tab
- hiển thị latency, provider, fallback, error rate
- giúp sản phẩm trông production-grade hơn nhiều

---

## 7. Thứ tự ưu tiên khuyến nghị

### Ưu tiên 1 - Bắt buộc
1. orchestrator
2. response schema chuẩn
3. observability + metrics
4. eval baseline

### Ưu tiên 2 - Tăng chất lượng lõi
1. transcript quality
2. prosody scoring
3. skill graph scorer
4. citation/evidence layer

### Ưu tiên 3 - Tăng khác biệt
1. inflation classifier
2. critic/verifier stage
3. Korean-specific retrieval/policies

### Ưu tiên 4 - Tối ưu trình diễn và scale
1. caching
2. async heavy scoring
3. dashboard đẹp cho admin/demo

---

## 8. Kế hoạch pitch theo từng mốc nâng cấp

### Sau Phase 1
Có thể pitch:
> "Our AI is grounded on recruiter rules and domain knowledge, not pure prompting."

### Sau Phase 2
Có thể pitch:
> "We combine LLM reasoning with specialist scoring models for transcript quality, prosody, and skill-graph matching."

### Sau Phase 3-4
Có thể pitch:
> "SpeakCV is an agentic hybrid AI system with evidence-backed evaluation, fallback, and measurable quality gains over prompt-only baselines."

### Sau Phase 5
Có thể pitch:
> "SpeakCV is optimized for Korean hiring and onboarding contexts, not just general interview practice."

---

## 9. Kết luận cuối
Nếu chỉ tinh chỉnh prompt thêm nữa, SpeakCV sẽ mạnh hơn nhưng vẫn bị nhìn như một LLM wrapper cao cấp. Để thật sự tiến lên Level 5, dự án cần đầu tư vào bốn trụ cột:

1. **Grounding**
2. **Specialized models**
3. **Agentic orchestration**
4. **Evaluation + observability**

Thứ tự hành động tốt nhất là:
- **chuẩn hóa kiến trúc trước**
- **thêm grounding và scoring services sau**
- **cuối cùng mới tối ưu hóa câu chuyện Level 5 để demo và pitch**

Nói ngắn gọn: SpeakCV đang ở vị trí rất tốt để nâng cấp, nhưng muốn được đánh giá cao theo chuẩn Level 5 thì phải chuyển từ “AI trả lời hay” sang “AI có hệ thống, có bằng chứng, có số liệu, và có chuyên môn hóa”.
