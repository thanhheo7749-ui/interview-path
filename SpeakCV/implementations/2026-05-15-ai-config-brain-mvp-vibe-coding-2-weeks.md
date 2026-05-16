# AI Config Brain — MVP Vibe Coding Plan (2 Weeks)

## Goal
Ship a working end-to-end flow for company interviewer brain:
- Upload `txt/md/docx`
- Auto parse into graph candidates
- Human review in AI Config
- Apply to draft version
- Publish and use in interview runtime

## MVP Scope (strict)
### In
1. File ingestion: `txt`, `md`, `docx`
2. Candidate generation:
   - node extraction
   - basic edge inference
   - confidence score per node/edge
3. Review gate in admin UI:
   - accept/reject/edit candidate
4. Draft apply + publish
5. Runtime prompt assembler reads active brain version

### Out
- `.doc` binary support
- Embedding retrieval
- Auto-learning from transcripts
- Complex governance workflows

## Architecture (simple)
- Backend FastAPI:
  - `IngestionController`
  - `IngestionService`
  - `GraphDraftService`
  - `PromptAssemblerService`
- Frontend Next.js:
  - AI Config tab with 3 panels: Upload/Versions, Graph canvas, Inspector
- DB tables (minimum):
  - `brain_versions`
  - `brain_nodes`
  - `brain_edges`
  - `brain_ingestion_jobs`
  - `brain_ingestion_candidates`

## API (MVP)
1. `POST /admin/ai-brain/ingestion/upload` (txt/md/docx)
2. `POST /admin/ai-brain/ingestion/jobs` (start parse)
3. `GET /admin/ai-brain/ingestion/jobs/{jobId}` (status/result)
4. `POST /admin/ai-brain/ingestion/jobs/{jobId}/apply-draft`
5. `POST /admin/ai-brain/ingestion/jobs/{jobId}/reject`
6. `POST /admin/ai-brain/publish/{version}`
7. `POST /admin/ai-brain/assemble-prompt` (preview)

## Parsing Rules (MVP)
### Node typing
- Contains “nên/phải/luôn” -> `principle`
- Contains “đánh giá/chấm” -> `rubric`
- Contains “không/tránh/cấm” -> `red_flag`
- Contains “nếu ... thì ...” -> `follow_up_strategy`
- Contains example question -> `question_pattern`

### Edge inference
- `supports`: supportive language
- `applies_to`: role/seniority mention
- `contradicts`: negative restriction

### Confidence
- High: clear keyword + clear structure
- Medium: one signal only
- Low: ambiguous paragraph

Low confidence defaults to unchecked in review UI.

## UI Flow (MVP)
1. Upload file
2. Show parsing status
3. Show candidate graph with badges (high/med/low)
4. Reviewer actions:
   - accept node/edge
   - reject node/edge
   - edit label/type/tags/weight
5. Apply to draft
6. Validate
7. Publish

## 2-Week Execution Plan

## Week 1 — Make it work
### Day 1-2
- DB migration + basic models for versions/nodes/edges/jobs/candidates
- File upload endpoint for txt/md/docx

### Day 3
- Implement extractor:
  - txt/md direct read
  - docx text extraction

### Day 4
- Implement parser + node typing rules + basic edge inference
- Save candidates to ingestion job

### Day 5
- Build job status endpoint + apply-draft endpoint
- Basic validation (id unique, edge endpoints exist)

## Week 2 — Make it usable
### Day 6-7
- Frontend upload + job status + candidate list

### Day 8
- Graph canvas render candidates + inspector edit

### Day 9
- Accept/reject/apply flow to draft version

### Day 10
- Publish flow + runtime assemble prompt preview
- Bugfix + smoke test + demo

## Acceptance Criteria (MVP Done)
1. Admin uploads `txt/md/docx` and gets parse result in under 30s (file <= 20k chars).
2. Candidate graph visible and editable in AI Config.
3. Apply writes accepted items into draft version only.
4. Publish switches active version successfully.
5. Interview runtime uses new active version for prompt assembly.

## Test Checklist
- Upload each format: txt/md/docx
- Parsing edge cases: long paragraph, bullet lists, mixed VN/EN
- Review gate: reject low-confidence nodes
- Publish rollback test (switch back to previous version)
- Runtime prompt token budget sanity check

## Risk Controls
- If parse fails: fallback to node-only import (no auto edges)
- If confidence low: force manual review
- If graph too noisy: batch reject + re-parse with strict mode

## Suggested Defaults
- `confidence_threshold=0.65`
- `max_chars_per_job=20000`
- `auto_edge=true` (high confidence only)
- `duplicate_similarity_threshold=0.88`

## Immediate Next Step
Implement backend ingestion first (upload -> parse -> job result) before graph UI polish.
