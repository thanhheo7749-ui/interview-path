# Sample companies

Two fictional companies used to demonstrate the Company Brain: `daehan-precision` (hierarchical, process driven)
and `sori-labs` (autonomous, written decisions).

- Every person, company, address and figure here is invented. None of it is real company data. Names carry "(Sample)"
  and email addresses use the `.sample` domain.
- The documents were drafted by subagents. The team must review and edit them to meet the contest's contribution rule
  before any submission.
- Each folder holds `company.yaml` (departments, users, documents), the Markdown documents, and `ground_truth.yaml`:
  the planted contradictions and gaps, plus the extraction used by the fake AI so seeding works with no AI keys.
  In `ground_truth.yaml`, omitted extraction fields default to `ref` = `title`, empty `body`, and `fact_kind: none`.
- `manager-notes.ko.md` is confidential on purpose and carries a canary string. It must never reach a candidate or
  employee answer.
- Run `make seed-samples ARGS=--auto-approve` (or `python -m app.cli seed-samples --auto-approve`). Auto-approve is
  refused for any company that is not a sample.
