# AI Config Brain Upgrade Plan (Hybrid Input + Graph Visualization)

## 1) Mục tiêu
Biến tab AI Config thành "bộ não người phỏng vấn" của công ty:
- Lưu tri thức/phong cách phỏng vấn theo domain công ty.
- Quản trị tri thức theo dạng graph (node/edge).
- Dùng graph này để sinh prompt ngữ cảnh cho interview runtime.
- Hỗ trợ **Hybrid input**: import JSON chuẩn + nhập/paste text (.txt/.md) + chỉnh tay trên UI.

## 2) Phạm vi v1 (YAGNI)
### In scope
- Data model cho Brain Graph (Node, Edge, BrainVersion).
- API CRUD cơ bản + import/export JSON.
- Auto Ingestion Agent: parse file text/docx/doc (doc convert) → draft graph.
- UI AI Config nâng cấp: editor metadata + graph canvas + validation.
- Runtime assembler: lấy subgraph liên quan để tạo system prompt động.
- Versioning nhẹ: publish version đang active.
- Human review gate bắt buộc trước khi apply/publish.

### Out of scope (v1)
- GNN training/inference thật sự trong backend.
- Auto-learning từ transcript chưa duyệt.
- Multi-tenant enterprise phức tạp.

## 3) 3 phương án thiết kế

## Phương án A — Rule Graph thuần (khuyến nghị cho v1)
- Node types: `principle`, `question_pattern`, `rubric`, `red_flag`, `follow_up_strategy`, `domain_knowledge`.
- Edge types: `supports`, `depends_on`, `contradicts`, `applies_to`, `escalates_to`.
- Runtime: truy vấn node theo interview context (job role, level, skill tags) rồi compile prompt.

**Ưu điểm**: dễ làm, dễ kiểm soát chất lượng, explainable.  
**Nhược điểm**: chưa có semantic scoring nâng cao.

## Phương án B — Knowledge Graph + Embedding Retrieval
- Giống A nhưng thêm embedding cho node text để semantic retrieval.

**Ưu điểm**: bám ngữ nghĩa tốt hơn.  
**Nhược điểm**: tăng chi phí/phức tạp, cần tuning.

## Phương án C — Graph-first với Neural scoring (pseudo-GNN)
- Thêm bước chấm điểm node relevance bằng heuristic nhiều tầng mô phỏng message passing.

**Ưu điểm**: demo “neural-like” tốt.  
**Nhược điểm**: over-engineer cho v1, khó debug.

### Recommendation
Chọn **A cho v1**, chuẩn bị schema tương thích để nâng cấp lên B ở v1.1.

## 4) Data contract đề xuất (Hybrid input)

## JSON import format (chuẩn)
```json
{
  "brain_name": "speakcv-interviewer-brain",
  "version": "2026.05.15",
  "nodes": [
    {
      "id": "n_principle_clear_feedback",
      "type": "principle",
      "label": "Feedback rõ ràng, không công kích",
      "content": "Luôn phản hồi cụ thể theo hành vi quan sát được.",
      "tags": ["communication", "culture"],
      "weight": 0.9,
      "active": true
    }
  ],
  "edges": [
    {
      "id": "e1",
      "source": "n_principle_clear_feedback",
      "target": "n_followup_behavioral",
      "type": "supports",
      "weight": 0.7
    }
  ],
  "meta": {
    "owner": "admin",
    "description": "Core interviewer brain"
  }
}
```

## Validation rules
- `id` unique toàn graph.
- Edge source/target phải tồn tại.
- `weight` trong [0,1].
- Chặn vòng lặp với edge loại `depends_on` (nếu business yêu cầu DAG).
- `content` tối thiểu 20 ký tự cho node tri thức.

## Text input contract (new)
- Input hỗ trợ: paste text, upload `.txt`, upload `.md`.
- Parser ưu tiên tách theo heading > bullet > paragraph.
- Mỗi đoạn ý chính ánh xạ 1 node; câu chứa tín hiệu quan hệ (`nếu`, `vì`, `do đó`, `tránh`) ánh xạ edge gợi ý.
- Cho phép user chọn mode parse:
  - `strict`: chỉ tạo node, không tự nối edge.
  - `assisted`: tạo node + edge gợi ý, user duyệt trước khi apply.
- Bắt buộc bước preview trước khi ghi vào draft graph.

## Mapping mặc định text → node type
- Principle/Guideline → `principle`
- Evaluation criteria/score hint → `rubric`
- Question template/example ask → `question_pattern`
- Avoid/forbidden behavior → `red_flag`
- If-then follow-up instruction → `follow_up_strategy`
- Domain-specific fact/process/tooling → `domain_knowledge`

## Heuristic relation mapping (assisted mode)
- Cụm từ `hỗ trợ`, `giúp` → `supports`
- Cụm từ `phụ thuộc`, `cần trước` → `depends_on`
- Cụm từ `không`, `tránh`, `cấm` → `contradicts`
- Cụm từ `áp dụng cho`, `đối với` → `applies_to`
- Cụm từ `nếu ... thì escalte/đẩy mức` → `escalates_to`

## Parse quality guardrails
- Nếu confidence parser < ngưỡng (vd 0.65), chỉ tạo node nháp, không auto-edge.
- Giới hạn 1 lần import text tối đa N ký tự (đề xuất 20k) để tránh graph nhiễu.
- Merge strategy theo fingerprint nội dung để tránh duplicate node.
- Bản ghi import giữ raw text + kết quả parse để audit/rollback.

## Text input examples
### Ví dụ 1: Paste
"Khi phỏng vấn backend senior, ưu tiên trade-off. Không hỏi trivia. Nếu ứng viên mơ hồ, follow-up bằng incident production."
- Nodes: principle(trade-off), red_flag(no trivia), follow_up_strategy(incident follow-up)
- Edges: principle `applies_to` follow_up_strategy, red_flag `contradicts` trivia-pattern

### Ví dụ 2: Markdown
- `## Rubric`
- `- Chấm cao nếu ứng viên nêu được quan sát + metric + quyết định.`
=> map sang `rubric` node với tags từ section title.

## 5) UX đề xuất cho tab AI Config

## Layout 3 cột
1. **Left panel**: Brain versions + import/export + publish.  
2. **Center panel**: Graph canvas (zoom/pan, drag node, filter type).  
3. **Right panel**: Node/Edge inspector (edit thuộc tính, tags, weight, guardrails).

## Core actions
- Import JSON → preview diff → apply.
- Import Text (`.txt/.md`) hoặc Paste Text → parse preview → apply.
- Add node/edge thủ công.
- Validate graph (lỗi hiển thị theo danh sách + highlight trực tiếp node lỗi).
- Save draft / Publish active version.
- Test prompt: nhập job context và xem assembled system prompt.
- Parse report: số node mới, số edge gợi ý, duplicate đã merge, cảnh báo low-confidence.

## 6) Runtime integration với interview
- Input runtime: `job_role`, `seniority`, `interview_mode`, `skill_tags`.
- Selector:
  1) lấy nodes theo tag + active version,
  2) expand 1-2 hops qua edges `supports/applies_to`,
  3) rank theo `weight`,
  4) cắt theo token budget.
- Output: system prompt động = guardrails + principles + question strategy + rubric snippets.

## 7) API v1 đề xuất
- `GET /admin/ai-brain/versions`
- `POST /admin/ai-brain/import`
- `POST /admin/ai-brain/import-text` (raw text / txt / md)
- `POST /admin/ai-brain/parse-text-preview`
- `POST /admin/ai-brain/ingestion/upload` (txt/docx/doc)
- `POST /admin/ai-brain/ingestion/jobs` (start parse job)
- `GET /admin/ai-brain/ingestion/jobs/{jobId}` (status/result)
- `POST /admin/ai-brain/ingestion/jobs/{jobId}/apply-draft`
- `POST /admin/ai-brain/ingestion/jobs/{jobId}/reject`
- `GET /admin/ai-brain/export?version=`
- `POST /admin/ai-brain/nodes`
- `PATCH /admin/ai-brain/nodes/{id}`
- `POST /admin/ai-brain/edges`
- `PATCH /admin/ai-brain/edges/{id}`
- `POST /admin/ai-brain/validate`
- `POST /admin/ai-brain/publish/{version}`
- `POST /admin/ai-brain/assemble-prompt` (preview)

## 7.1) Auto Ingestion Agent (new)
### Mục tiêu
Tự động chuyển tài liệu tri thức phỏng vấn thành draft graph chất lượng cao, giảm thao tác tay nhưng vẫn có kiểm soát.

### Pipeline
1. Upload file (`.txt`, `.md`, `.docx`, `.doc`).  
2. Preprocess:
   - Convert `.doc` -> `.docx`.
   - Extract text + heading structure.
   - Normalize Unicode, remove boilerplate.
3. Segment:
   - Chia theo heading > bullet > paragraph.
4. Classify:
   - Gán node type theo rule + LLM classifier (nếu bật).
5. Linking:
   - Tạo edge candidate bằng heuristic relation mapping.
6. Confidence scoring:
   - Tính score cho node/edge, đánh dấu low-confidence.
7. Duplicate handling:
   - Fingerprint + similarity để merge candidate trùng.
8. Draft output:
   - Ghi vào ingestion result (không ghi thẳng active graph).
9. Human review gate:
   - Admin duyệt/sửa trước khi `apply-draft`.

### Output contract
- `job_id`, `source_file`, `parse_summary`
- `candidate_nodes[]` (kèm `confidence`, `reason`)
- `candidate_edges[]` (kèm `confidence`, `reason`)
- `duplicates[]` (auto-merge đề xuất)
- `warnings[]` (thiếu cấu trúc, đoạn mơ hồ, confidence thấp)

### Review & apply rules
- Node/edge `confidence < 0.65` mặc định unchecked.
- `depends_on` edge phải qua cycle check trước apply.
- Apply chỉ ghi vào **draft version** đang chọn.
- Publish vẫn yêu cầu validate toàn graph pass.

### Guardrails
- Giới hạn file size và ký tự parse mỗi job.
- Timeout + retry policy cho parser/LLM.
- Lưu raw extraction để audit và tái hiện lỗi parse.
- Role-based access: chỉ admin mới được apply/publish.

### Acceptance criteria (v1)
- >= 85% node type đúng trên bộ test tài liệu nội bộ.
- <= 5% duplicate node sau auto-merge trên sample chuẩn.
- 100% ingestion job đi qua review gate trước publish.
- Thời gian từ upload đến draft preview <= 30s với file <= 20k chars.

### Non-goals (v1)
- Không tự publish.
- Không tự học online từ transcript production.
- Không can thiệp trực tiếp runtime khi chưa publish version mới.

### Quan hệ với Graph UI
- Graph canvas hiển thị candidate bằng màu riêng (draft-layers).
- Inspector cho phép accept/reject từng node/edge hoặc batch theo confidence.
- Parse report hiển thị rõ: created/merged/rejected/pending-review.

### Fallback strategy
- Nếu parser lỗi hoặc confidence quá thấp:
  - Chuyển sang chế độ node-only import.
  - Tắt auto-edge và yêu cầu user nối tay.
  - Cảnh báo chất lượng ngay trong preview.

### Security
- Scan định dạng và mime-type trước extract.
- Chặn macro/script nhúng trong tài liệu office.
- Sanitize text trước khi đưa vào LLM để tránh prompt injection qua tài liệu.

### Telemetry
- Theo dõi: parse latency, accept-rate, reject-rate, post-publish correction-rate.
- Dùng telemetry để tuning heuristic mapping và ngưỡng confidence.

### Operational runbook
- Nếu job stuck > timeout: cho phép cancel + retry.
- Nếu parse sai hàng loạt: rollback draft version + bật strict mode tạm thời.
- Nếu duplicate tăng cao: nâng ngưỡng similarity và bắt buộc tag taxonomy.

### Suggested internal components
- `DocumentExtractor` (doc/docx/txt)
- `BrainSegmenter`
- `NodeClassifier`
- `EdgeInferencer`
- `ConfidenceScorer`
- `DuplicateResolver`
- `IngestionOrchestrator`
- `IngestionReviewService`

### Suggested data tables
- `brain_ingestion_jobs`
- `brain_ingestion_candidates`
- `brain_ingestion_warnings`
- `brain_ingestion_audit_logs`

### Suggested frontend states
- `uploaded` -> `parsing` -> `ready_for_review` -> `applied_to_draft` / `rejected`
- UI luôn hiển thị trạng thái job realtime tại tab AI Config.

### Suggested rollout
- Milestone A: txt/md only + manual review
- Milestone B: docx/doc support + duplicate merge
- Milestone C: classifier tuning + confidence dashboard

### Definition of done (ingestion)
- Upload file thành công.
- Preview graph candidate hiển thị đầy đủ.
- Admin apply vào draft version.
- Validate pass và publish được version mới.
- Interview runtime dùng đúng version sau publish.

### Example flow
1) Admin upload `backend_interview_guideline.docx`.
2) Agent trả 42 nodes, 35 edges, 8 low-confidence.
3) Admin reject 3 edge, sửa 2 tags, accept phần còn lại.
4) Apply vào draft `2026.05.15-rc1`.
5) Validate pass, publish, runtime dùng version mới.

### KPI bổ sung cho ingestion
- Tỷ lệ approve candidate ngay lần đầu > 75%.
- Tỷ lệ chỉnh tay sau apply < 20%.
- Tỷ lệ rollback do parse sai < 5%.

### Decision log
- Chọn kiến trúc asynchronous job cho ingestion thay vì sync request để tránh timeout với docx lớn.
- Chọn review gate bắt buộc để đảm bảo governance chất lượng interviewer brain.
- Chọn apply vào draft thay vì active để giảm rủi ro runtime regression.

### Open questions cho v1.1
- Có bật semantic embedding ngay ở ingestion hay để phase sau?
- Có hỗ trợ multi-language parsing (VI/EN mixed) ở mức classifier không?
- Có cần policy template theo từng phòng ban (Engineering/Sales/Product)?

### Recommended default config
- `parse_mode=assisted`
- `confidence_threshold=0.65`
- `max_chars_per_job=20000`
- `auto_edge=true` (chỉ cho confidence cao)
- `duplicate_similarity_threshold=0.88`

### Team workflow đề xuất
- Content owner chuẩn bị tài liệu theo template.
- Admin upload + review candidate graph.
- Tech lead approve publish.
- Theo dõi KPI 1 tuần, rồi tuning threshold.

### Governance rule
- Mọi ingestion job phải gắn `owner`, `source`, `purpose`.
- Không publish version mới nếu chưa có ít nhất 1 reviewer khác owner.
- Audit log giữ tối thiểu 90 ngày.

### Expected impact
- Rút ngắn onboarding tri thức phỏng vấn từ hàng giờ xuống vài phút.
- Tăng tính nhất quán interviewer behavior giữa các vòng.
- Giảm phụ thuộc chỉnh prompt tay thủ công.

### Exit criteria cho phase ingestion v1
- Đã chạy pilot với ít nhất 3 tài liệu nội bộ.
- KPI tối thiểu đạt ngưỡng acceptance.
- Team admin có checklist vận hành ingestion rõ ràng.
- Không phát sinh sự cố runtime sau publish trong 2 tuần pilot.

### Pilot plan
- Tuần 1: 1 tài liệu guideline chung.
- Tuần 2: 1 tài liệu rubric backend + 1 tài liệu behavioral.
- Tuần 3: review KPI, tuning threshold, chốt baseline.

### Quick checklist cho reviewer
- Node type đúng chưa?
- Tags có đúng taxonomy không?
- Edge có hợp lý và không mâu thuẫn không?
- Có duplicate rõ ràng chưa merge không?
- Có node nào quá mơ hồ cần tách nhỏ không?

### Quick checklist cho publisher
- Validate graph pass.
- Prompt preview không vượt budget.
- A/B sanity test với 3 kịch bản interview.
- Audit info đầy đủ (owner/source/reviewer).
- Release note version đã ghi nhận.

### Change management
- Mọi thay đổi ngưỡng confidence phải có changelog.
- Mọi lỗi parse nghiêm trọng phải mở incident nội bộ và cập nhật heuristic.
- Version brain quan trọng phải có backup export JSON trước publish.

### Documentation artifacts
- Template nhập liệu `.md/.docx` cho content team.
- Runbook ingestion cho admin.
- Rubric đánh giá chất lượng parse hàng tuần.

### Long-term extension (post-v1)
- Thêm semantic retrieval để cải thiện candidate linking.
- Thêm suggestion agent đề xuất missing node theo lỗ hổng graph.
- Thêm policy engine để enforce compliance/culture constraints tự động.

### Final recommendation
Giữ Auto Ingestion Agent ở mức rule-first + review-gated trong v1 để tối ưu độ ổn định, sau đó nâng dần semantic intelligence dựa trên telemetry thực tế.

## 8) Lộ trình triển khai
- Phase 1 thêm ingestion API cơ bản trước UI hoàn chỉnh.
- Phase 2 hoàn thiện review UX và duplicate merge.
- Phase 3 tuning chất lượng parse dựa trên KPI production.
- Phase 4 bổ sung semantic intelligence nếu KPI cho thấy cần thiết.

## Phase 1 — Foundation
- DB schema + migration cho brain graph.
- API import/export/validate.
- API parse-text-preview + import-text.
- Tạo seed graph mẫu.

## Phase 2 — Admin UX
- Graph canvas + inspector + version panel.
- Workflow save draft/publish.
- Text ingestion wizard (paste/upload → parse preview → apply).

## Phase 3 — Runtime
- Prompt assembler tích hợp vào luồng interview.
- Telemetry: log nodes được chọn + token usage.

## Phase 4 — Hardening
- Permission admin, audit log thay đổi.
- Snapshot rollback nhanh theo version.
- Parse quality metrics + tuning heuristics theo dữ liệu thực.

## 9) Rủi ro & giảm thiểu
- **Graph rác, nhập sai chuẩn** → import preview + strict validator.
- **Text parse sai ngữ nghĩa** → assisted mode + confidence gate + bắt buộc review trước apply.
- **Prompt quá dài** → rank + truncation theo token budget.
- **Config tốt nhưng kết quả interview lệch** → A/B test theo version brain.
- **UI graph nặng** → virtual rendering + giới hạn node render theo cluster/filter.

## 10) KPI thành công
- 100% phiên interview dùng active brain version.
- >70% tri thức mới được onboard qua flow import text trong <10 phút/lần cập nhật.
- Giảm thời gian chỉnh prompt thủ công >50%.
- Tăng tính nhất quán đánh giá interviewer (variance rubric score giảm).
- Không vượt token budget backend đã cấu hình.

## 11) Quy tắc nhập dữ liệu khuyến nghị (để team dùng ngay)
1. Mỗi node chỉ chứa **một ý rõ ràng**.  
2. Dùng tags theo taxonomy cố định (`skill`, `culture`, `seniority`, `role`).  
3. Nội dung node viết ngắn, mệnh lệnh rõ, tránh mơ hồ.  
4. `weight` chỉ dùng 3 mức chuẩn: 0.4 / 0.7 / 0.9 để dễ governance.  
5. Với text import, luôn duyệt parse preview trước khi apply.  
6. Mọi thay đổi lớn phải qua draft + publish version mới, không sửa trực tiếp bản active.

---
**Kết luận:** v1 nên đi theo Rule Graph thuần (Approach A) với Hybrid input (JSON + Text + Manual) để ra sản phẩm nhanh, dễ kiểm soát; giữ cửa nâng cấp semantic retrieval ở v1.1.

## 8) Lộ trình triển khai

## Phase 1 — Foundation
- DB schema + migration cho brain graph.
- API import/export/validate.
- API parse-text-preview + import-text.
- Tạo seed graph mẫu.

## Phase 2 — Admin UX
- Graph canvas + inspector + version panel.
- Workflow save draft/publish.
- Text ingestion wizard (paste/upload → parse preview → apply).

## Phase 3 — Runtime
- Prompt assembler tích hợp vào luồng interview.
- Telemetry: log nodes được chọn + token usage.

## Phase 4 — Hardening
- Permission admin, audit log thay đổi.
- Snapshot rollback nhanh theo version.
- Parse quality metrics + tuning heuristics theo dữ liệu thực.

## 9) Rủi ro & giảm thiểu
- **Graph rác, nhập sai chuẩn** → import preview + strict validator.
- **Text parse sai ngữ nghĩa** → assisted mode + confidence gate + bắt buộc review trước apply.
- **Prompt quá dài** → rank + truncation theo token budget.
- **Config tốt nhưng kết quả interview lệch** → A/B test theo version brain.
- **UI graph nặng** → virtual rendering + giới hạn node render theo cluster/filter.

## 10) KPI thành công
- 100% phiên interview dùng active brain version.
- >70% tri thức mới được onboard qua flow import text trong <10 phút/lần cập nhật.
- Giảm thời gian chỉnh prompt thủ công >50%.
- Tăng tính nhất quán đánh giá interviewer (variance rubric score giảm).
- Không vượt token budget backend đã cấu hình.

## 11) Quy tắc nhập dữ liệu khuyến nghị (để team dùng ngay)
1. Mỗi node chỉ chứa **một ý rõ ràng**.  
2. Dùng tags theo taxonomy cố định (`skill`, `culture`, `seniority`, `role`).  
3. Nội dung node viết ngắn, mệnh lệnh rõ, tránh mơ hồ.  
4. `weight` chỉ dùng 3 mức chuẩn: 0.4 / 0.7 / 0.9 để dễ governance.  
5. Với text import, luôn duyệt parse preview trước khi apply.  
6. Mọi thay đổi lớn phải qua draft + publish version mới, không sửa trực tiếp bản active.

---
**Kết luận:** v1 nên đi theo Rule Graph thuần (Approach A) với Hybrid input (JSON + Text + Manual) để ra sản phẩm nhanh, dễ kiểm soát; giữ cửa nâng cấp semantic retrieval ở v1.1.

## 5) UX đề xuất cho tab AI Config

## Layout 3 cột
1. **Left panel**: Brain versions + import/export + publish.  
2. **Center panel**: Graph canvas (zoom/pan, drag node, filter type).  
3. **Right panel**: Node/Edge inspector (edit thuộc tính, tags, weight, guardrails).

## Core actions
- Import JSON → preview diff → apply.
- Add node/edge thủ công.
- Validate graph (lỗi hiển thị theo danh sách + highlight trực tiếp node lỗi).
- Save draft / Publish active version.
- Test prompt: nhập job context và xem assembled system prompt.

## 6) Runtime integration với interview
- Input runtime: `job_role`, `seniority`, `interview_mode`, `skill_tags`.
- Selector:
  1) lấy nodes theo tag + active version,
  2) expand 1-2 hops qua edges `supports/applies_to`,
  3) rank theo `weight`,
  4) cắt theo token budget.
- Output: system prompt động = guardrails + principles + question strategy + rubric snippets.

## 7) API v1 đề xuất
- `GET /admin/ai-brain/versions`
- `POST /admin/ai-brain/import`
- `GET /admin/ai-brain/export?version=`
- `POST /admin/ai-brain/nodes`
- `PATCH /admin/ai-brain/nodes/{id}`
- `POST /admin/ai-brain/edges`
- `PATCH /admin/ai-brain/edges/{id}`
- `POST /admin/ai-brain/validate`
- `POST /admin/ai-brain/publish/{version}`
- `POST /admin/ai-brain/assemble-prompt` (preview)

## 8) Lộ trình triển khai

## Phase 1 — Foundation
- DB schema + migration cho brain graph.
- API import/export/validate.
- Tạo seed graph mẫu.

## Phase 2 — Admin UX
- Graph canvas + inspector + version panel.
- Workflow save draft/publish.

## Phase 3 — Runtime
- Prompt assembler tích hợp vào luồng interview.
- Telemetry: log nodes được chọn + token usage.

## Phase 4 — Hardening
- Permission admin, audit log thay đổi.
- Snapshot rollback nhanh theo version.

## 9) Rủi ro & giảm thiểu
- **Graph rác, nhập sai chuẩn** → import preview + strict validator.
- **Prompt quá dài** → rank + truncation theo token budget.
- **Config tốt nhưng kết quả interview lệch** → A/B test theo version brain.
- **UI graph nặng** → virtual rendering + giới hạn node render theo cluster/filter.

## 10) KPI thành công
- 100% phiên interview dùng active brain version.
- Giảm thời gian chỉnh prompt thủ công >50%.
- Tăng tính nhất quán đánh giá interviewer (variance rubric score giảm).
- Không vượt token budget backend đã cấu hình.

## 11) Quy tắc nhập dữ liệu khuyến nghị (để team dùng ngay)
1. Mỗi node chỉ chứa **một ý rõ ràng**.  
2. Dùng tags theo taxonomy cố định (`skill`, `culture`, `seniority`, `role`).  
3. Nội dung node viết ngắn, mệnh lệnh rõ, tránh mơ hồ.  
4. `weight` chỉ dùng 3 mức chuẩn: 0.4 / 0.7 / 0.9 để dễ governance.  
5. Mọi thay đổi lớn phải qua draft + publish version mới, không sửa trực tiếp bản active.

---
**Kết luận:** v1 nên đi theo Rule Graph thuần (Approach A) với Hybrid input để ra sản phẩm nhanh, dễ kiểm soát; giữ cửa nâng cấp semantic retrieval ở v1.1.