# SpeakCV Level 5 Gap Analysis

## 1. Mục tiêu đánh giá
Tài liệu này đối chiếu trạng thái hiện tại của SpeakCV với tiêu chí Level 5 trong [ideamvp.md](../ideamvp.md):
- LLM chỉ là một phần của core engine
- Có grounding / data riêng / explainability
- Có agentic workflow
- Có specialized models ngoài LLM
- Có guardrails, evaluation, realtime, fallback
- Có yếu tố Korean-specific rõ ràng

Kết luận ngắn: SpeakCV hiện đã có nền tảng tốt ở mức **Level 2.5 đến 3** và có vài mầm mống của Level 4, nhưng **chưa đạt Level 5**. Hệ thống hiện vẫn chủ yếu là **prompt-driven LLM application** với một số heuristic module đi kèm, chưa phải hybrid AI architecture hoàn chỉnh.

---

## 2. Bằng chứng hiện trạng trong codebase

### 2.1 Những gì đã có
1. **LLM integration thực tế**
   - Provider layer có Gemini primary + OpenAI fallback trong [src/backend/app/ai_service.py](../src/backend/app/ai_service.py).
   - Nhiều flow AI đã chạy production cho interview, CV review, CV makeover, CV tailor.

2. **Speech pipeline cơ bản**
   - Audio transcription đang dùng Groq Whisper trong [src/backend/app/routers/interview.py](../src/backend/app/routers/interview.py).
   - Có kiểm tra chất lượng transcript tiếng Anh bằng heuristic `_english_transcript_is_low_quality`.

3. **Adaptive interview logic bước đầu**
   - Có `knowledge_graph.py` và `nunchi_analyzer.py` trong [src/backend/core/](../src/backend/core/).
   - Interview prompt được gắn thêm context động về intent, confidence, next topic trong [src/backend/app/routers/interview.py](../src/backend/app/routers/interview.py).

4. **Guardrails prompt-level cho CV**
   - Có prompt cấm hallucination, cấm thêm kỹ năng ảo trong [src/backend/app/routers/cv_prompts.py](../src/backend/app/routers/cv_prompts.py).
   - Có JSON schema-oriented output cho CV makeover/tailor.

5. **Streaming và fallback bước đầu**
   - CV review dùng streaming response trong [src/backend/app/routers/cv.py](../src/backend/app/routers/cv.py).
   - AI provider fallback giữa Gemini và OpenAI đã tồn tại trong [src/backend/app/ai_service.py](../src/backend/app/ai_service.py).

### 2.2 Những gì còn mang tính wrapper/prompt-centric
1. **Business logic AI vẫn chủ yếu nằm trong prompt**
   - CV review ở [src/backend/app/routers/cv.py](../src/backend/app/routers/cv.py) chỉ lấy text CV + JD rồi gửi thẳng vào LLM để chấm ATS.
   - End-interview report ở [src/backend/app/routers/interview.py](../src/backend/app/routers/interview.py) vẫn phụ thuộc gần như hoàn toàn vào một prompt rất dài.

2. **Heuristic modules chưa trở thành hybrid pipeline thực sự**
   - `knowledge_graph.py` là graph tĩnh trong memory, chưa dùng data người dùng, chưa có retrieval, chưa có scoring độc lập đủ mạnh.
   - `nunchi_analyzer.py` là regex/filler heuristic, chưa phải specialized model.

3. **Chưa có orchestration layer rõ ràng**
   - Chưa thấy `orchestrator` hay multi-step controller riêng biệt; router đang tự nối các bước với nhau.
   - Chưa có trace chuẩn cho từng step trong pipeline.

---

## 3. Đánh giá theo 10 tiêu chí Level 5 trong ideamvp.md

## 3.1 Không chỉ là wrapper quanh ChatGPT / LLM
**Trạng thái:** Đạt một phần.

**Điểm có:**
- Có nhiều flow AI khác nhau, không chỉ một prompt duy nhất.
- Có module phụ trợ như knowledge graph, transcript quality heuristic, nunchi analysis.

**Thiếu:**
- Các module phụ trợ chưa đủ mạnh để trở thành core engine độc lập với prompt.
- Nhiều quyết định chính vẫn do LLM quyết định trực tiếp từ raw input.

**Kết luận:**
- SpeakCV vượt qua Level 1 rõ ràng.
- Nhưng vẫn chưa ra khỏi vùng “LLM app with supporting heuristics”.

## 3.2 Có data / knowledge riêng (RAG hoặc KG)
**Trạng thái:** Chưa đạt.

**Điểm có:**
- Có `knowledge_graph.py`, nhưng đây là graph kỹ thuật tĩnh cho frontend topics.

**Thiếu:**
- Chưa có vector DB, retrieval layer, company knowledge corpus, Korean business culture corpus, recruiter memory, JD taxonomy store.
- Chưa có citation/evidence trả ngược về UI.
- Chưa có data store cho explainable grounding.

**Kết luận:**
- Đây là một gap rất lớn vì grounding là điều kiện gần như bắt buộc để lên top-level trong hackathon AI thực dụng.

## 3.3 Có ít nhất 1 specialized model ngoài LLM
**Trạng thái:** Chưa đạt production-level.

**Điểm có:**
- Có Whisper transcription API qua Groq trong [interview.py](../src/backend/app/routers/interview.py).
- Có heuristic transcript quality check.

**Thiếu:**
- Whisper hiện mới là external ASR service, chưa được đóng gói như một scoring component trong pipeline hybrid.
- Chưa có prosody model, classifier, ranking model, embedding model domain-specific, hoặc graph scorer độc lập.
- `nunchi_analyzer.py` chưa phải model học máy.

**Kết luận:**
- Có tín hiệu multi-model nhưng chưa đạt mức “specialized models are part of core architecture”.

## 3.4 Agentic workflow / multi-step planning
**Trạng thái:** Có mầm mống, chưa đạt.

**Điểm có:**
- Interview flow đã có vài bước: transcript -> intent/confidence heuristic -> topic selection -> prompt generation -> LLM reply.

**Thiếu:**
- Chưa có nhiều agent chuyên trách như Extractor, Verifier, Matcher, Critic.
- Chưa có planning loop, self-reflection, retry-by-step, critic stage, decision trace.
- Chưa có persistent task memory cho các agent.

**Kết luận:**
- Hiện tại là dynamic prompting pipeline, chưa phải agentic orchestration.

## 3.5 Output có explanation rõ ràng
**Trạng thái:** Đạt một phần.

**Điểm có:**
- CV review trả markdown có Match Percentage, Missing Keywords, Detailed Feedback.
- Interview report có `evaluation` và `ideal_answer` trong JSON report.

**Thiếu:**
- Chưa có evidence-backed explanation.
- Chưa có citation tới JD spans, CV spans, policy source, company docs.
- Chưa có reasoning trace tách lớp scoring và lớp explanation.

**Kết luận:**
- Có “explanation text”, nhưng chưa có “defensible explainability”.

## 3.6 Guardrails / safety
**Trạng thái:** Trung bình.

**Điểm có:**
- Guardrails prompt-level cho CV tailoring.
- Có vài limit cơ bản như guest turn cap trong [interview.py](../src/backend/app/routers/interview.py).

**Thiếu:**
- Chưa thấy PII redaction pipeline cho CV raw text.
- Chưa thấy bias detection cho CV ranking/interview scoring.
- Chưa có policy enforcement layer tách khỏi prompt.
- Chưa có moderation / safety audit log / confidence-based refusal.

**Kết luận:**
- Mức guardrails hiện tại chưa đủ để thuyết phục ban giám khảo doanh nghiệp.

## 3.7 Evaluation / benchmark số liệu
**Trạng thái:** Chưa đạt.

**Điểm có:**
- Chưa thấy eval suite hay benchmark report trong code đọc được.

**Thiếu:**
- Không có offline eval set cho CV-JD matching.
- Không có recruiter-labeled benchmark.
- Không có transcript quality benchmark.
- Không có dashboard precision/recall/latency/cost.

**Kết luận:**
- Đây là gap cực lớn. Nếu không có benchmark, rất khó claim top 5%.

## 3.8 Demo realtime / latency dưới 3s
**Trạng thái:** Đạt một phần.

**Điểm có:**
- Có streaming CV review.
- Interview chat/audio có tính chất thời gian thực.

**Thiếu:**
- Chưa thấy measurement p50/p95 latency theo route.
- Chưa thấy optimization layer như caching, batching, async step orchestration, fast-path scoring.
- Chưa có chứng cứ dưới 3 giây ổn định trên stage.

**Kết luận:**
- Có realtime feel, nhưng chưa có realtime discipline.

## 3.9 Fallback khi AI fail
**Trạng thái:** Đạt mức cơ bản.

**Điểm có:**
- Gemini -> OpenAI fallback trong [ai_service.py](../src/backend/app/ai_service.py).
- Một vài route có fallback text khi lỗi.

**Thiếu:**
- Chưa có step-level fallback cho transcript, graph scoring, explanation, report generation.
- Chưa có degrade modes rõ ràng: no-audio-score mode, no-grounding mode, no-citation mode.
- Chưa có observability để biết fallback xảy ra bao nhiêu lần.

**Kết luận:**
- Có nền tảng tốt, nhưng chưa đủ production-grade.

## 3.10 Korean-specific element rõ ràng
**Trạng thái:** Rất yếu.

**Điểm có:**
- ideamvp nhấn mạnh South Korean business context, nhưng trong code hiện tại dấu hiệu này chưa rõ.

**Thiếu:**
- Chưa thấy Korean business culture corpus.
- Chưa có formality/politeness classifier cho tiếng Hàn/English-to-Korean business adaptation.
- Chưa có recruiter/company policy grounding cho bối cảnh Hàn.
- Chưa có scenario đặc thù: Korean HR interview norms, honorific formality, onboarding etiquette, work-culture suggestions.

**Kết luận:**
- Đây là điểm yếu chiến lược nếu mục tiêu là gây ấn tượng với ban giám khảo doanh nghiệp Hàn.

---

## 4. Mapping theo khung 5 level của ideamvp

### Level 1 - AI Wrapper
SpeakCV **đã vượt qua** mức này.

### Level 2 - AI + Prompt Engineering
SpeakCV **đạt chắc** mức này.
- Có prompt tách file cho CV.
- Có JSON mode.
- Có multi-step prompting nhẹ.

### Level 3 - AI + RAG / Tool Use
SpeakCV **mới chạm mép**, chưa đạt đầy đủ.
- Có tool-like modules, nhưng thiếu retrieval/data moat thật sự.
- Chưa có RAG/citation.

### Level 4 - Agentic Workflow / Multi-agent
SpeakCV **có mầm mống** nhưng chưa đủ.
- Có dynamic prompting + graph-based topic shift.
- Chưa có multi-agent orchestration, critic loop, memory, planner.

### Level 5 - Specialized Models / Hybrid Architecture
SpeakCV **chưa đạt**.
- Chưa có specialized model layer chạy như first-class component.
- Chưa có eval-driven hybrid pipeline.

**Đánh giá tổng quát:**
> Nếu demo hiện tại, SpeakCV phù hợp để kể câu chuyện “strong Level 2, early Level 3, experimental Level 4 hints”. Chưa nên tự claim Level 5.

---

## 5. Các chi tiết cần cải thiện để tiến gần Level 5

## 5.1 Kiến trúc AI
1. Tách `router -> orchestrator -> specialist services -> explainer`.
2. Mỗi route AI cần có `decision_trace_id` và step logs.
3. Chuyển heuristic modules thành service contracts ổn định.

## 5.2 Grounding / data moat
1. Thêm RAG cho JD, recruiter rubric, company policy, Korean work-culture docs.
2. Thêm citation block trong output.
3. Lưu chunk metadata để explainability có thể truy vết.

## 5.3 Specialized models
1. Interview Coach:
   - prosody scorer
   - transcript confidence scorer
   - nervousness / fluency classifier
2. CV Matcher:
   - skill graph scorer
   - CV inflation classifier
   - domain embedding reranker

## 5.4 Agentic workflow
1. CV flow nên tách thành:
   - Extractor
   - Matcher
   - Verifier
   - Explainer
   - Critic
2. Interview flow nên có:
   - Listener
   - Transcript QA
   - Topic Planner
   - Response Coach
   - Evaluator

## 5.5 Explainability
1. Mọi score nên có `reason` và `evidence`.
2. Tách `raw score` khỏi `natural-language explanation`.
3. UI nên hiển thị matched skills, missing prerequisites, inflation signals.

## 5.6 Guardrails
1. PII redaction trước khi log CV/interview text.
2. Bias audit cho CV scoring.
3. Confidence threshold để từ chối hoặc yêu cầu xác nhận transcript.
4. Structured policy checks ngoài prompt.

## 5.7 Evaluation
1. Tạo eval set 100-300 CV/JD pairs có nhãn recruiter.
2. Tạo eval set audio EN/VI nhiều accent.
3. Log cost, latency, fallback rate.
4. Có bảng so sánh baseline vs hybrid.

## 5.8 Korean-specific differentiation
1. Corpus về Korean business etiquette.
2. Formality / politeness adaptation layer.
3. Scenario bank theo Korean interview style.
4. Company-specific onboarding and communication guidance.

---

## 6. Ưu tiên nâng cấp theo tác động

### Nhóm A - Phải có để thoát khỏi Level 2/3
1. Orchestrator layer
2. RAG + citation
3. Eval suite
4. Structured observability

### Nhóm B - Phải có để kể câu chuyện Level 5
1. Prosody scoring
2. Skill graph scorer
3. Inflation classifier
4. Critic / verifier stage

### Nhóm C - Phần tạo khác biệt trên sân khấu
1. Korean-specific intelligence
2. Realtime explainability UI
3. Admin hybrid metrics dashboard

---

## 7. Kết luận cuối
SpeakCV hiện **không thiếu ý tưởng**, mà thiếu **kiến trúc AI có thể defend được**. Repo đã có nền tốt để nâng cấp: provider abstraction, interview flow, transcription, graph heuristic, prompt guardrails. Tuy nhiên để đạt Level 5 theo chuẩn trong [ideamvp.md](../ideamvp.md), dự án cần chuyển từ:

- **prompt-centric app**
- sang **hybrid, grounded, observable, benchmarked AI system**

Nói ngắn gọn:
- **Đã có nền để pitch là AI product nghiêm túc**
- **Chưa đủ bằng chứng để pitch là top-5% Level 5 system**
- **Cần nâng cấp mạnh nhất ở 4 điểm: grounding, specialized models, orchestration, evaluation**
