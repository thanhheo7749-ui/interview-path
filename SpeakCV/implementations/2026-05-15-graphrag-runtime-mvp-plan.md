# GraphRAG Runtime MVP Plan (Interview Flow)

## Objective
Integrate GraphRAG-style retrieval into interview runtime so prompt context is assembled from relevant subgraph instead of static top-node selection.

## Scope (MVP)
- Runtime retrieval only for `/api/chat` flow.
- Source graph: active AI Brain version (`ai_brain_versions`, `ai_brain_nodes`, `ai_brain_edges`).
- Retrieval inputs: `jd_text`, `mode`, detected language, `user_text`, optional skill tags inferred from conversation.
- Output: dynamic context block injected before AI call.

## Out of Scope
- Vector DB / external embedding service.
- Multi-hop advanced graph ranking beyond 2 hops.
- Rebuilding admin ingestion UX.

## Current-State Findings
- Chat runtime entrypoint: `src/backend/app/routers/interview.py` (`/api/chat`).
- Current prompt assembly is rule-based (base prompt + cognitive directives), no graph retrieval.
- AI Brain management endpoints exist in `src/backend/app/routers/admin.py` and data tables already available in `sql_models.py`.

## Target Runtime Architecture
1. `chat` receives request.
2. Build retrieval query features from request:
   - role/domain terms from `jd_text`
   - latest user utterance (`user_text`)
   - interview mode
3. Fetch active brain version.
4. Retrieve candidate seed nodes by lexical match + type weighting.
5. Expand neighborhood (1-hop default, optional 2-hop cap).
6. Rank and trim to token budget.
7. Build `brain_context_block` and append into system prompt.
8. Send to existing AI provider via `call_ai_chat`.

## Implementation Phases

### Phase 1 — Graph Retrieval Core (Backend utility layer)
Files:
- `src/backend/app/core/brain_retrieval.py` (new)

Tasks:
- Implement `get_active_brain_version(db)`.
- Implement `build_query_terms(chat_request)`.
- Implement `retrieve_seed_nodes(db, version_id, terms)`:
  - match on `label`, `content`, `tags` (case-insensitive contains).
- Implement `expand_subgraph(db, version_id, seed_node_keys, hop=1, max_nodes=40, max_edges=80)`.
- Implement `rank_nodes(nodes, terms)` with simple score:
  - text match + node weight + confidence prior.
- Implement `assemble_brain_context(nodes, edges, max_chars)`.

Verification:
- Unit-style smoke function returns non-empty context when active version has matching nodes.

### Phase 2 — Runtime Integration in `/api/chat`
Files:
- `src/backend/app/routers/interview.py`

Tasks:
- Import retrieval utility.
- In `chat`, after base prompt + language policy, call retrieval pipeline.
- Append context block under explicit section header:
  - `[BRAIN CONTEXT - RETRIEVED SUBGRAPH]`
- Add graceful fallback:
  - if no active version or no match, continue with existing prompt flow.
- Add lightweight debug log (non-sensitive): selected node count, edge count, context chars.

Verification:
- `/api/chat` still responds when graph retrieval fails.
- `/api/chat` includes retrieved context when active graph exists and terms match.

### Phase 3 — Prompt Budget and Quality Guards
Files:
- `src/backend/app/routers/interview.py`
- `src/backend/app/core/brain_retrieval.py`

Tasks:
- Add runtime char budget for retrieved context (e.g., 2,500–4,000 chars configurable).
- Prioritize node types for interview quality (`principle`, `rubric`, `red_flag` first).
- De-duplicate repetitive lines.
- Ensure language consistency in retrieved lines (respect current EN/VI policy).

Verification:
- Context stays within budget.
- No duplicated repeated bullets in assembled prompt.

### Phase 4 — Observability and Admin Validation Hook
Files:
- `src/backend/app/routers/interview.py`
- optional: `src/backend/app/models.py` (if returning debug metadata in a safe mode)

Tasks:
- Add optional debug flag (env-driven) to log retrieval summary.
- Keep production response payload unchanged for MVP.
- Prepare one admin-side manual test checklist.

Verification:
- Debug logs visible when enabled, silent when disabled.

## Data/Scoring Strategy (MVP)
- Seed score:
  - +3 exact keyword in label
  - +2 keyword in tags
  - +1 keyword in content
  - +weight bonus (`node.weight * 0.5`)
- Expansion:
  - include direct neighbors through edges.
- Final sort:
  - seed score desc, then node weight desc.

## API/Contract Changes
- No mandatory external API contract changes for frontend in MVP.
- Internal only: `/api/chat` prompt assembly enriched server-side.

## Test Plan
1. **Happy path**: Active version exists with relevant backend nodes; chat question about latency/SLO retrieves expected principles/rubrics.
2. **No graph**: No active version; chat behavior remains unchanged.
3. **No match**: Active graph exists but unrelated query; fallback to base prompt only.
4. **Performance**: Retrieval adds acceptable latency (target <120ms DB-side for moderate graph).
5. **Language policy**: EN mode yields EN response policy preserved.

## Risks & Mitigations
- Risk: noisy retrieval harms answer quality.
  - Mitigation: type-priority ranking + budget cap + dedupe.
- Risk: latency spikes on large graphs.
  - Mitigation: cap seeds/nodes/edges, 1-hop default.
- Risk: overfitting to keyword contains.
  - Mitigation: keep scoring modular for later embedding upgrade.

## Rollout
- Step 1: implement behind env flag `AI_ENABLE_BRAIN_RETRIEVAL=1`.
- Step 2: validate with seed file (`implementations/brain_seed.md`).
- Step 3: enable by default after QA pass.

## Acceptance Criteria
- `/api/chat` successfully uses retrieved brain context when enabled.
- Interview responses demonstrably reference relevant principles/rubrics for matching topics.
- Existing chat flow remains stable when retrieval unavailable.
- Runtime overhead remains acceptable for MVP.
