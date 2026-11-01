# Block 2: Company Brain Design

Parent: [Product Overview](2026-11-01-hiring-platform-overview-design.md). Depends on [Block 1](2026-11-01-block-1-foundation-design.md).

## Goal

A per-company knowledge graph built from real documents, approved by HR, enforced by permission layers, and queried with citations. Policy Copilot (contest idea 4) and Contradiction Radar (#7) prove it works. The API for Ask the Company (#13) ships here.

## 1. Permission layers

Three layers: `public`, `internal`, `confidential`.

| Audience | May read |
|---|---|
| Candidate | public |
| Employee | public, internal |
| Manager | public, internal, confidential nodes in their department subtree |
| HR | all |

Rules:

- **Filtering happens in the database query**, in one retriever module. Content above an audience's level never reaches a prompt, so the design does not rely on telling the model to keep secrets.
- `Audience` is built on the server from the membership, never from a request parameter. The HR-only "view as" option in the graph explorer simulates an audience read-only through the same filter.
- A document has a visibility, and its chunks inherit it. A node has its own visibility. HR may publish a public node from an internal document: the node text is then public, but its source is shown as "Company document (not shared)".
- An edge is visible only if both end nodes are visible.

## 2. Data model

All tables carry `company_id`.

```
kb_documents        id, company_id, department_id NULL, title, language, source_type (upload|intake),
                    file_path, visibility, effective_date NULL, uploaded_by, status, created_at
kb_ingestion_jobs   id, document_id, status (queued|running|review|failed|done), progress, error, created_at
kb_chunks           id, company_id, document_id, position, page NULL, text, embedding BLOB,
                    embedding_model, embedding_dim
kb_nodes            id, company_id, department_id NULL, type, title, body, language, visibility,
                    status (draft|published|rejected|superseded), effective_date NULL,
                    fact_kind NULL, fact_value NULL, fact_unit NULL, scope_text NULL,
                    embedding BLOB, embedding_model, embedding_dim,
                    approved_by NULL, approved_at NULL, created_at
kb_node_sources     id, node_id, chunk_id, quote
kb_edges            id, company_id, source_node_id, target_node_id, relation, status
kb_conflicts        id, company_id, node_a_id, node_b_id, status (open|resolved|dismissed),
                    resolution NULL, resolved_by NULL, resolved_at NULL, created_at
assistant_questions id, company_id, user_id NULL, audience, question, language, answered,
                    top_score, embedding BLOB, embedding_model, resolved, created_at
```

Embeddings are little-endian float32. Every vector stores its model; retrieval refuses to compare across models. `make reembed` regenerates vectors after a vendor change, because embedding spaces are incompatible.

### Node types

`company`, `department`, `role`, `requirement`, `skill`, `value`, `behavior`, `policy`, `process`, `fact`, `private_note`.

### Relations

| Relation | From → To |
|---|---|
| `part_of` | department → company, department → department |
| `has_role` | department → role |
| `requires` | role → requirement or skill, with `must_have` attribute |
| `holds` | company or department → value |
| `shown_by` | value → behavior |
| `expects` | role → behavior |
| `applies_to` | policy or process → company, department or role |
| `states` | policy → fact |
| `has_note` | role → private_note |

Default layers, which HR can change: role, requirement, skill, value, behavior are public; policy, process, fact are internal; private_note, covering dealbreakers and salary bands, is confidential.

`company` and `department` nodes are created by code, one per row of the Block 1 tables, and stay in sync with them. AI extraction cannot create those two types; it links to them instead.

## 3. Ingestion pipeline

Runs as a FastAPI background job with a progress bar. On startup, jobs left in `running` become `failed` with a retry button.

1. **Upload.** PDF, DOCX, TXT, MD up to `MAX_UPLOAD_MB`. HR sets department, default visibility and language, guessed from Unicode ranges. PDFs with no extractable text fail with a clear message; OCR is out of scope.
2. **Chunk.** Split on headings and paragraphs: target 1,200 characters, 150 overlap, page number kept. Embed with the `embedding` slot, `kind="document"`.
3. **Extract.** `generate_structured` on the `bulk` slot per chunk. Output: nodes, edges, facts, each with a verbatim `quote`. Document text is delimited and treated as data, not instructions.
4. **Verify.** After normalising Unicode and whitespace, a quote not found in its chunk causes the item to be dropped and counted. This is the anti-fabrication gate.
5. **Merge.** Same type and same normalised title merge sources. Same type with embedding cosine of at least 0.90 is proposed to HR as a merge.
6. **Contradiction check.** Section 5.
7. **Review.** Items wait as `draft`.
8. **Publish.** HR accepts, edits, rejects, or changes layer, per item or in bulk per document. Accepting sets `approved_by` and increments `companies.kb_version`.

Only `published` nodes are used anywhere.

## 4. Retrieval

Module `app/brain/retriever.py`. Nothing else queries `kb_*` for AI context.

### Free-text search

```python
def search(company_id, audience, query, top_k=8) -> ContextBundle
```

1. Embed the query with `kind="query"`.
2. Load allowed nodes and chunks. Compare in Python using a NumPy matrix cached per company and model, invalidated when `kb_version` changes.
3. Keyword score: NFKC, casefold, Unicode `\w+` tokens, and character bigrams for Hangul, using a BM25-style score. This fixes the old ASCII-only matching that broke Vietnamese and dropped Korean.
4. Combined score: `0.7 * cosine + 0.3 * keyword`, tuned by evaluation.
5. Expand from top nodes by 1 to 2 hops over visible edges.
6. Return a `ContextBundle` of nodes, chunks and citations, with open-conflict flags and a best score, within a character budget.

### Role profile

```python
def role_profile(company_id, audience, role_node_id) -> RoleProfile
```

No search: walk the graph from the role to its requirements, team values, and expected behaviours. This powers Block 3 and is why one CV produces different interviews at two companies.

## 5. Contradiction Radar (#7)

Compact scope: facts of kind `number`, `date` or `boolean`.

1. For each new fact, find existing published or draft facts of the same kind with cosine of at least 0.80. This works across languages.
2. Skip pairs whose normalised values match, decided by code.
3. For the rest, a `generate_structured` call answers: same topic? same scope? Cross-language is handled here.
4. Same topic, same scope and different values opens a `kb_conflicts` row.
5. HR chooses A, chooses B, or marks "different scope, no conflict". The losing fact becomes `superseded`.

While a conflict is open, Copilot does not assert either value.

Known limits: only explicit conflicts are found, and false alarms arise when documents legitimately differ by scope. That is why the "different scope" action exists.

## 6. Policy Copilot (contest idea 4) and Ask the Company (#13)

One engine with a different audience.

```
POST /api/companies/{id}/copilot/ask     any member, audience from membership
POST /api/public/companies/{slug}/ask    logged-in user, audience=candidate, rate limited
```

Ask the Company requires login to limit cost abuse; the limit is 20 questions per hour per user.

Flow:

1. `search` for context.
2. If the best score is under the threshold, record the question as unanswered and return the "could not find this, passed to HR" message in the asker's language. Thresholds are stored per embedding model, because score scales differ.
3. If a top fact has an open conflict, return a template in the asker's language stating that two sources differ and HR is confirming, citing both, with no LLM call.
4. Otherwise `generate_structured` on the `reasoning` slot returns `can_answer`, `answer`, `citation_ids`, answering only from context, in the question's language.
5. Code checks that `citation_ids` exist in the bundle. If not, retry once, then treat as unanswered.
6. Response includes document title, page and effective date, for sources the audience may see.

Every question is logged to `assistant_questions`. There is no ticketing system: unanswered questions feed the gap list.

## 7. Gap list

HR sees unanswered questions grouped by topic, greedy clustering at cosine of at least 0.80, as "documents to write", with counts. HR can mark a group resolved.

## 8. API

Under `/api/companies/{id}/kb/`, HR only unless noted:

```
POST   documents                 upload, starts a job
GET    documents                 list with job status
GET    jobs/{job_id}             progress
POST   jobs/{job_id}/retry
GET    review?document_id=       draft nodes, edges, merge proposals
POST   review/decide             bulk accept, edit, reject, change layer
GET    conflicts                 open conflicts
POST   conflicts/{id}/resolve
GET    gaps
POST   gaps/{group}/resolve
GET    graph?view_as=            nodes and edges; view_as is HR-only
```

## 9. Portal UI

- **Documents**: upload with progress.
- **Review queue**: per-item accept, edit, reject and layer change, with the source quote.
- **Graph explorer**: reuse `KnowledgeGraph.jsx`, replacing `mockGraph.js` with API data. Nodes are coloured by layer. The **view-as switch** shows nodes disappearing for a candidate or employee. This is a Q&A demo moment.
- **Conflicts**, with both sources side by side.
- **Gaps**, with counts.
- **Copilot** chat for all members, with citations, in three states: answered, conflict, not found.

Delete `data/mockGraph.js` and the canned "Upload Knowledge" flow.

## 10. Sample companies

Under `SpeakCV/src/backend/seed/sample_companies/`:

| | Daehan Precision Vina (Sample) | Sori Labs (Sample) |
|---|---|---|
| Type | Subsidiary of a Korean conglomerate, strict process, hierarchical reporting | Korean startup, autonomous, few levels |
| Shared role | Backend Developer | Backend Developer |

Documents: handbook in Korean and Vietnamese, values, team playbook, English JD, leave and bonus policies, including **planted contradictions** (some across Korean and Vietnamese) and **planted gaps**, recorded in `ground_truth.yaml`. Names always carry "(Sample)" and may be renamed by the team.

Subagents draft the documents. **The team reviews and edits them** to meet the contest's contribution rule.

`python -m app.cli seed-samples` runs the real pipeline. `--auto-approve` is accepted only for companies with `is_sample=true`.

## 11. Evaluation

`make eval-brain` calls real AI and costs money, so it prints an estimate and asks for confirmation. It is not part of `make test`. It writes a report to `eval/reports/`, and can run per provider profile to compare vendors.

The question set in `eval/brain/` has 30 questions, 10 each in Vietnamese, English and Korean: 20 answerable and 10 not covered by any document.

| Check | How | Target |
|---|---|---|
| Permission leak | Canary strings in confidential documents must never appear in prompt context for candidate or employee | **0, required** |
| Company isolation | Ask at A about content only B has | **0, required** |
| Citation accuracy | Cited chunk contains the answer, against ground truth | ≥ 90% |
| Correct refusal | Uncovered questions are declined | ≥ 90% |
| Contradiction recall | Planted conflicts found | ≥ 80% |

Targets are goals. Only measured values go on slides.

Permission leak and company isolation also run in `make test` using the `fake` provider, asserting on the assembled prompt.

## 12. Error handling

| Failure | Behaviour |
|---|---|
| Extraction fails on a chunk | Retry per gateway rules, then mark that chunk failed and continue; the job shows a partial warning |
| Embedding service down | Job fails with retry; nothing partial is published |
| Search with no embeddings under current model | Clear error telling the operator to run `make reembed` |
| AI down during Copilot | Honest error message; never a fabricated answer |

## 13. Testing

Unit tests with the `fake` provider: quote verification, audience filter matrix, hop expansion visibility, cross-model refusal, conflict state machine, citation validation, Hangul and Vietnamese tokenisation. Add the Block 1 enumeration test coverage for all new routes. Playwright: upload, review, publish, and ask with fake AI.

## 14. Acceptance criteria

1. An HR user uploads a document and gets draft nodes with verified quotes; publishing makes them available to Copilot.
2. Permission leak and company isolation evaluations both report 0.
3. The view-as switch shows correct filtering.
4. Copilot shows all three states, in all three languages.
5. Planted contradictions appear in the conflict screen; resolving one changes the answers.
6. Repeated unanswered questions appear in the gap list.
7. An evaluation report exists with measured citation, refusal and recall numbers.
8. `mockGraph.js` is gone.

## 15. Out of scope

OCR, a dedicated vector database, ticketing, candidate-facing UI (Block 3), implicit contradiction detection.
