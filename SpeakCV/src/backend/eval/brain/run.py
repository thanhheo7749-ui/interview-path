"""Company Brain evaluation harness.

Measures permission leaks, company isolation, citation accuracy, correct refusal and Contradiction Radar recall
against the labelled ground truth of the two fictional sample companies. Permission leaks also count probes of text
planted in a public document whose chunk sources a confidential or rejected node.

    python -m eval.brain.run [--yes] [--dry-run] [--profile fake|env]

The run always uses a throwaway SQLite file, never the app's configured database. It prints an estimated cost
before any AI call and needs --yes or a typed confirmation when it could spend money.
Under the fake provider the numbers come from fixtures and prove the mechanism only. They measure no real AI quality.
"""
import argparse
import json
import os
import secrets
import shutil
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import yaml

EVAL_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = EVAL_DIR.parents[1]
QUESTIONS_PATH = EVAL_DIR / "questions.yaml"
REPORTS_DIR = BACKEND_ROOT / "eval" / "reports"
SAMPLES_DIR = BACKEND_ROOT / "seed" / "sample_companies"

SLOTS = ("reasoning", "bulk", "embedding", "stt", "tts")
AUDIENCES_UNDER_LEAK_CHECK = ("candidate", "employee")
TARGETS = {
    "permission_leak": ("==", 0),
    "company_isolation": ("==", 0),
    "citation_accuracy": (">=", 0.90),
    "correct_refusal": (">=", 0.90),
    "contradiction_recall": (">=", 0.80),
}

# Assumptions behind the estimate. They are printed with it, so nobody mistakes them for measurements.
INPUT_TOKENS_PER_QUESTION = 3000
OUTPUT_TOKENS_PER_QUESTION = 500
QUERY_EMBED_TOKENS = 40
CHARS_PER_TOKEN = 3
EXTRACTION_PROMPT_TOKENS_PER_DOCUMENT = 800
OUTPUT_TOKENS_PER_NODE = 120
EMBED_TOKENS_PER_NODE = 100
CONFLICT_CHECKS_PER_PLANTED_PAIR = 3
CONFLICT_CHECK_INPUT_TOKENS = 600
CONFLICT_CHECK_OUTPUT_TOKENS = 20
# One candidate and one employee answer per sample company, plus the planted text and their extra searches.
PROBE_ANSWERS_PER_COMPANY = 2
PROBE_EMBED_TOKENS_PER_COMPANY = 400

PROBE_DOCUMENT_TITLE = "Backend Developer job advert (eval probe)"
PROBE_SENTENCE = "The relocation allowance band for the Backend Developer role is 30 to 40 million. {canary}"
PROBE_QUESTION = "What is the relocation allowance band for the Backend Developer role?"
STRADDLING_DOCUMENT_TITLE = "Backend Developer relocation memo (eval probe)"
STRADDLING_QUOTE = (
    "The relocation allowance band for the Backend Developer role, as agreed by the compensation committee and "
    "reviewed by the board of directors last quarter, is 30 to 40 million. {canary} per month."
)
STRADDLING_FILLER = "This paragraph is neutral filler for the evaluation and says nothing about the topic asked. "
# Long enough that the chunker cuts hard windows, and the second window starts inside the quote, before the canary.
STRADDLING_HEAD_CHARS = 1080
STRADDLING_TAIL_CHARS = 1400

FIXTURE_NOTE = (
    "This run used the fake AI provider for at least one slot. Its numbers come from fixtures and the deterministic "
    "fake provider. They prove the mechanism works and do not measure real AI quality."
)


class EvalError(RuntimeError):
    pass


def load_questions(path: Path = QUESTIONS_PATH) -> list[dict]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or []


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_truth() -> dict[str, dict]:
    """Per sample company: ground truth, document texts by title, and all document text."""
    truth = {}
    for folder in sorted(p for p in SAMPLES_DIR.iterdir() if (p / "company.yaml").is_file()):
        spec = _load_yaml(folder / "company.yaml")
        by_title = {
            entry["title"]: (folder / entry["file"]).read_text(encoding="utf-8") for entry in spec.get("documents", [])
        }
        truth[folder.name] = {
            "truth": _load_yaml(folder / "ground_truth.yaml"),
            "documents": by_title,
            "text": "\n".join(by_title.values()),
        }
    return truth


# ---------------------------------------------------------------------------------------------------------------
# Markers
# ---------------------------------------------------------------------------------------------------------------

def canaries(truth: dict[str, dict]) -> list[str]:
    return [canary for company in truth.values() for canary in company["truth"].get("canaries", [])]


def isolation_markers(truth: dict[str, dict], company: str) -> list[str]:
    """Text that only the other companies hold. A prompt for `company` must never contain any of it.

    Markers are the other companies' canaries, any line they list under `isolation_markers` in ground_truth.yaml,
    and every ground truth quote that does not also appear in this company's own documents.
    """
    from app.brain.text import quote_in

    own_text = truth[company]["text"]
    markers: list[str] = []
    for slug, other in truth.items():
        if slug == company:
            continue
        data = other["truth"]
        markers += data.get("canaries", [])
        markers += data.get("isolation_markers", [])
        quotes = [item["quote"] for item in data.get("extraction", []) + data.get("edges", [])]
        quotes += [pair[side]["quote"] for pair in data.get("contradictions", []) for side in ("a", "b")]
        markers += [quote for quote in quotes if not quote_in(quote, own_text)]
    return list(dict.fromkeys(marker for marker in markers if marker.strip()))


def contains_any(text: str, markers: list[str]) -> list[str]:
    from app.brain.text import quote_in

    return [marker for marker in markers if quote_in(marker, text)]


# ---------------------------------------------------------------------------------------------------------------
# Estimate
# ---------------------------------------------------------------------------------------------------------------

def _tokens(chars: int) -> int:
    return -(-chars // CHARS_PER_TOKEN)


def estimate(question_count: int, truth: dict[str, dict], seeding: bool) -> dict:
    """Estimated cost of the run, built from stated assumptions. `complete` is False when any price is unknown."""
    from app.ai.config import get_config
    from app.ai.types import Usage
    from app.ai.usage import estimate_cost

    config = get_config()
    reasoning, bulk, embedding = (config.slot(name) for name in ("reasoning", "bulk", "embedding"))
    lines = [
        {
            "label": f"{question_count} Copilot answers", "slot": "reasoning", "provider": reasoning.provider,
            "model": reasoning.model,
            "usage": Usage(input_tokens=question_count * INPUT_TOKENS_PER_QUESTION,
                           output_tokens=question_count * OUTPUT_TOKENS_PER_QUESTION),
        },
        {
            "label": f"{question_count} question embeddings", "slot": "embedding", "provider": embedding.provider,
            "model": embedding.model, "usage": Usage(input_tokens=question_count * QUERY_EMBED_TOKENS),
        },
    ]
    companies = len(truth)
    lines += [
        {
            "label": "public document leak probes, answers", "slot": "reasoning", "provider": reasoning.provider,
            "model": reasoning.model,
            "usage": Usage(input_tokens=companies * PROBE_ANSWERS_PER_COMPANY * INPUT_TOKENS_PER_QUESTION,
                           output_tokens=companies * PROBE_ANSWERS_PER_COMPANY * OUTPUT_TOKENS_PER_QUESTION),
        },
        {
            "label": "public document leak probes, embeddings", "slot": "embedding", "provider": embedding.provider,
            "model": embedding.model, "usage": Usage(input_tokens=companies * PROBE_EMBED_TOKENS_PER_COMPANY),
        },
    ]
    if seeding:
        documents = sum(len(company["documents"]) for company in truth.values())
        doc_tokens = sum(_tokens(len(text)) for company in truth.values() for text in company["documents"].values())
        nodes = sum(len(company["truth"].get("extraction", [])) for company in truth.values())
        pairs = sum(len(company["truth"].get("contradictions", [])) for company in truth.values())
        checks = pairs * CONFLICT_CHECKS_PER_PLANTED_PAIR
        lines += [
            {
                "label": f"extraction over {documents} sample documents", "slot": "bulk", "provider": bulk.provider,
                "model": bulk.model,
                "usage": Usage(input_tokens=doc_tokens + documents * EXTRACTION_PROMPT_TOKENS_PER_DOCUMENT,
                               output_tokens=nodes * OUTPUT_TOKENS_PER_NODE),
            },
            {
                "label": f"{checks} contradiction checks", "slot": "bulk", "provider": bulk.provider,
                "model": bulk.model,
                "usage": Usage(input_tokens=checks * CONFLICT_CHECK_INPUT_TOKENS,
                               output_tokens=checks * CONFLICT_CHECK_OUTPUT_TOKENS),
            },
            {
                "label": "embeddings of chunks and nodes", "slot": "embedding", "provider": embedding.provider,
                "model": embedding.model, "usage": Usage(input_tokens=doc_tokens + nodes * EMBED_TOKENS_PER_NODE),
            },
        ]
    total, unpriced = 0.0, []
    for line in lines:
        cost = estimate_cost(line["model"], line["usage"])
        line["cost_usd"] = cost
        if cost is None:
            unpriced.append(line["label"])
        else:
            total += cost
    return {
        "lines": lines, "total_usd": total, "complete": not unpriced, "unpriced": unpriced, "seeding": seeding,
        "fixture": any(slot.provider == "fake" for slot in (reasoning, bulk, embedding)),
    }


def format_estimate(est: dict) -> str:
    out = ["Estimated cost before any AI call (assumptions, not measurements):"]
    for line in est["lines"]:
        usage = line["usage"]
        price = "price unknown" if line["cost_usd"] is None else f"${line['cost_usd']:.4f}"
        out.append(
            f"  - {line['label']}: {line['provider']}/{line['model']} ({line['slot']}), "
            f"{usage.input_tokens} input + {usage.output_tokens} output tokens, {price}"
        )
    if not est["seeding"]:
        out.append("  - seeding skipped: the sample companies are already present.")
    out.append(
        f"  Assumed per question: {INPUT_TOKENS_PER_QUESTION} input and {OUTPUT_TOKENS_PER_QUESTION} output tokens on the "
        f"reasoning model, {QUERY_EMBED_TOKENS} embedding tokens. Seeding assumes ~{CHARS_PER_TOKEN} characters per token."
    )
    if est["complete"]:
        out.append(f"  Total: ${est['total_usd']:.4f}")
    else:
        out.append(
            f"  Total: AT LEAST ${est['total_usd']:.4f}. PARTIAL: no price is known for {', '.join(est['unpriced'])}, "
            "so the real cost is higher than this figure."
        )
    if est["fixture"]:
        out.append("  Fake provider in use: no money is spent.")
    return "\n".join(out)


# ---------------------------------------------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------------------------------------------

@contextmanager
def capture_prompts():
    """Record `system` and `messages` of every text or structured generation, then delegate unchanged."""
    from app.ai import gateway

    captured: list[str] = []
    original_text, original_structured = gateway.generate_text, gateway.generate_structured

    def record(system, messages):
        captured.append((system or "") + "\n" + "\n".join(str(m.get("content", "")) for m in messages))

    def text(slot, system, messages, *args, **kwargs):
        record(system, messages)
        return original_text(slot, system, messages, *args, **kwargs)

    def structured(slot, system, messages, *args, **kwargs):
        record(system, messages)
        return original_structured(slot, system, messages, *args, **kwargs)

    gateway.generate_text, gateway.generate_structured = text, structured
    try:
        yield captured
    finally:
        gateway.generate_text, gateway.generate_structured = original_text, original_structured


def _apply_profile(profile: str) -> None:
    from app.ai.config import reset_config

    if profile == "fake":
        for slot in SLOTS:
            os.environ[f"AI_{slot.upper()}_PROVIDER"] = "fake"
    elif profile != "env":
        raise EvalError(f"Unknown profile '{profile}'. Use 'fake' or 'env' (the providers set in the environment).")
    reset_config()


def _require_sqlite() -> None:
    from app.database.database import engine

    if engine.url.get_backend_name() != "sqlite":
        raise EvalError("The harness only runs on a SQLite database. Run it through `python -m eval.brain.run`.")


def _seeded(db, slugs) -> bool:
    from app.database.sql_models import Company, KbDocument

    for slug in slugs:
        company = db.query(Company).filter_by(slug=slug).first()
        if company is None or not db.query(KbDocument.id).filter_by(company_id=company.id).first():
            return False
    return True


def _ask(db, question: dict, company_id: int) -> dict:
    from app.brain import copilot
    from app.brain.audience import Audience

    audience = Audience(company_id=company_id, kind=question["audience"])
    with capture_prompts() as prompts:
        try:
            response = copilot.ask(db, audience, question["question"], None)
        except Exception as exc:  # A failed AI call is an error for this question, not the end of the run.
            db.rollback()
            return {"state": "error", "error": f"{type(exc).__name__}: {exc}", "answer": "", "citations": [],
                    "prompt": "\n".join(prompts)}
    return {
        "state": response.state, "error": None, "answer": response.answer,
        "citations": [citation.title for citation in response.citations], "prompt": "\n".join(prompts),
    }


def _score_question(question: dict, result: dict, truth: dict[str, dict], all_canaries: list[str],
                    markers: dict[str, list[str]]) -> dict:
    from app.brain.text import quote_in

    visible_output = result["answer"] + "\n" + "\n".join(result["citations"])
    leaked = []
    if question["audience"] in AUDIENCES_UNDER_LEAK_CHECK:
        leaked = contains_any(result["prompt"], all_canaries) + contains_any(visible_output, all_canaries)
    crossed = contains_any(result["prompt"], markers[question["company"]])

    cited_ok = None
    if question["covered"]:
        documents = truth[question["company"]]["documents"]
        cited_ok = any(
            quote_in(question["expected_quote"], documents.get(title, "")) for title in result["citations"]
        )
    refused = None if question["covered"] else result["state"] == "not_found"
    return {
        "id": question["id"], "company": question["company"], "language": question["language"],
        "audience": question["audience"], "covered": question["covered"], "probe": question.get("probe"),
        "state": result["state"], "error": result["error"], "citations": result["citations"],
        "citation_ok": cited_ok, "refused_correctly": refused,
        "permission_leak": sorted(set(leaked)), "company_isolation": sorted(set(crossed)),
    }


def _probe_canaries(slug: str) -> dict[str, str]:
    marker = slug.upper()
    return {
        "confidential": f"CANARY-PUBLIC-DOC-{marker}-CONFIDENTIAL-2208",
        "rejected": f"CANARY-PUBLIC-DOC-{marker}-REJECTED-2208",
        "straddling": f"CANARY-PUBLIC-DOC-{marker}-STRADDLING-2208",
    }


def plant_public_document_probe(db, company_id: int, slug: str) -> None:
    """Plant text a document's own layer does not protect: a public document saying what HR classed as hidden.

    One chunk sources a published confidential note and the other a rejected node. Lives only in the throwaway
    database, because the sample documents are the labelled ground truth of the other measures.
    """
    from app.ai import gateway
    from app.brain import vectors
    from app.database.sql_models import KbChunk, KbDocument, KbNode, KbNodeSource

    if db.query(KbDocument.id).filter_by(company_id=company_id, title=PROBE_DOCUMENT_TITLE).first():
        return
    document = KbDocument(company_id=company_id, title=PROBE_DOCUMENT_TITLE, language="en", visibility="public",
                          status="published")
    db.add(document)
    db.flush()
    planted = _probe_canaries(slug)
    sides = [("confidential", "published", "confidential"), ("rejected", "rejected", "public")]
    texts = [PROBE_SENTENCE.format(canary=planted[name]) for name, _, _ in sides]
    embedded = gateway.embed(texts, "document", "kb_embed", company_id)
    for position, ((_, status, visibility), text, vector) in enumerate(zip(sides, texts, embedded.vectors)):
        chunk = KbChunk(company_id=company_id, document_id=document.id, position=position, text=text,
                        embedding=vectors.encode(vector), embedding_model=embedded.model,
                        embedding_dim=embedded.dimension)
        node = KbNode(company_id=company_id, type="private_note", title=f"Relocation note {position}", body="",
                      language="en", visibility=visibility, status=status)
        db.add_all([chunk, node])
        db.flush()
        db.add(KbNodeSource(node_id=node.id, chunk_id=chunk.id, quote=text))
    db.commit()
    plant_straddling_probe(db, company_id, planted["straddling"])


def plant_straddling_probe(db, company_id: int, canary: str) -> None:
    """A confidential quote that crosses a chunk boundary, linked the way ingestion links it. The canary is in the tail,
    so the chunk that starts inside the quote says it without holding the whole quote."""
    from app.ai import gateway
    from app.brain import vectors
    from app.brain.chunking import chunk_pages
    from app.brain.ingestion import chunks_sharing_quote
    from app.database.sql_models import KbChunk, KbDocument, KbNode, KbNodeSource

    quote = STRADDLING_QUOTE.format(canary=canary)
    head = (STRADDLING_FILLER * 20)[:STRADDLING_HEAD_CHARS]
    tail = (STRADDLING_FILLER * 20)[:STRADDLING_TAIL_CHARS]
    pieces = [chunk.text for chunk in chunk_pages([(None, f"{head} {quote} {tail}")])]
    if not any(quote in text for text in pieces) or not any(canary in text and quote not in text for text in pieces):
        raise EvalError("The straddling probe no longer crosses a chunk boundary.")
    document = KbDocument(company_id=company_id, title=STRADDLING_DOCUMENT_TITLE, language="en", visibility="public",
                          status="published")
    node = KbNode(company_id=company_id, type="private_note", title="Relocation note straddling", body="", language="en",
                  visibility="confidential", status="published")
    db.add_all([document, node])
    db.flush()
    embedded = gateway.embed(pieces, "document", "kb_embed", company_id)
    rows = [
        KbChunk(company_id=company_id, document_id=document.id, position=position, text=text,
                embedding=vectors.encode(vector), embedding_model=embedded.model, embedding_dim=embedded.dimension)
        for position, (text, vector) in enumerate(zip(pieces, embedded.vectors))
    ]
    db.add_all(rows)
    db.flush()
    db.add_all([KbNodeSource(node_id=node.id, chunk_id=rows[index].id, quote=quote)
                for index in chunks_sharing_quote(quote, pieces)])
    db.commit()


def public_document_probes(db, company_ids: dict[str, int], all_canaries: list[str]) -> tuple[bool, list[dict]]:
    """Ask for the planted text as each audience under check. Also returns whether HR's search can reach it.

    A leak counts in the retrieved context as well as the prompt and the answer, so it does not depend on the
    relevance gate letting the question through. If HR cannot reach the chunk, finding no leak would prove nothing.
    """
    from app.brain import retriever
    from app.brain.audience import Audience

    reachable = True
    probes = []
    for slug, company_id in company_ids.items():
        hr_items = retriever.search(db, Audience(company_id, "hr"), PROBE_QUESTION).items
        hr_text = "\n".join(i.text for i in hr_items)
        planted = _probe_canaries(slug)
        reachable = reachable and all(contains_any(hr_text, [planted[name]]) for name in ("confidential", "straddling"))
        for kind in AUDIENCES_UNDER_LEAK_CHECK:
            result = _ask(db, {"audience": kind, "question": PROBE_QUESTION}, company_id)
            retrieved = "\n".join(i.text for i in retriever.search(db, Audience(company_id, kind), PROBE_QUESTION).items)
            seen = "\n".join((retrieved, result["prompt"], result["answer"], *result["citations"]))
            probes.append({"company": slug, "audience": kind, "state": result["state"],
                           "leaked": sorted(set(contains_any(seen, all_canaries)))})
    return reachable, probes


def contradiction_recall(db, truth: dict[str, dict]) -> tuple[float, list[dict]]:
    from app.brain.text import quote_in
    from app.database.sql_models import Company, KbConflict, KbNodeSource

    def holds(quotes: list[str], planted: str) -> bool:
        return any(quote_in(planted, quote) or quote_in(quote, planted) for quote in quotes)

    details = []
    for slug, company_truth in truth.items():
        company = db.query(Company).filter_by(slug=slug).first()
        conflicts = [] if company is None else db.query(KbConflict).filter(
            KbConflict.company_id == company.id, KbConflict.status.in_(("open", "resolved"))
        ).all()
        cache: dict[int, list[str]] = {}

        def quotes_of(node_id: int) -> list[str]:
            if node_id not in cache:
                cache[node_id] = [row.quote for row in db.query(KbNodeSource.quote).filter_by(node_id=node_id)]
            return cache[node_id]

        for pair in company_truth["truth"].get("contradictions", []):
            found = any(
                (holds(quotes_of(c.node_a_id), pair["a"]["quote"]) and holds(quotes_of(c.node_b_id), pair["b"]["quote"]))
                or (holds(quotes_of(c.node_a_id), pair["b"]["quote"]) and holds(quotes_of(c.node_b_id), pair["a"]["quote"]))
                for c in conflicts
            )
            details.append({"company": slug, "topic": pair["topic"], "found": found})
    total = len(details)
    return (sum(d["found"] for d in details) / total if total else 0.0), details


def _actual_cost(db, since_id: int) -> tuple[float, bool]:
    from app.database.sql_models import AIUsageLog

    rows = db.query(AIUsageLog.estimated_cost_usd).filter(AIUsageLog.id > since_id).all()
    return sum(r[0] for r in rows if r[0] is not None), any(r[0] is None for r in rows)


def _ratio(hits: int, total: int) -> float:
    return hits / total if total else 0.0


def evaluate(profile: str = "env", confirm: Callable[[str, dict], bool] | None = None, dry_run: bool = False,
             reports_dir: Path | None = REPORTS_DIR, questions: list[dict] | None = None,
             before_questions: Callable | None = None) -> dict | None:
    """Run the harness. Returns the report dictionary, or None when it stopped before spending (dry run or declined).

    `before_questions(db)` runs after seeding and before the first question. Tests use it to plant a canary.
    """
    _require_sqlite()
    _apply_profile(profile)
    from app.ai.config import get_config
    from app.brain import retriever, seed
    from app.database.database import SessionLocal
    from app.database.sql_models import AIUsageLog, Company
    from sqlalchemy import func

    questions = load_questions() if questions is None else questions
    truth = load_truth()
    db = SessionLocal()
    try:
        est = estimate(len(questions), truth, seeding=not _seeded(db, truth))
        print(format_estimate(est))
        if dry_run:
            print("Dry run: nothing was seeded and no AI call was made.")
            return None
        if confirm is None or not confirm(format_estimate(est), est):
            print("Not confirmed: no AI call was made.")
            return None

        start_id = db.query(func.coalesce(func.max(AIUsageLog.id), 0)).scalar()
        seed.seed_samples(auto_approve=True)
        # seed_samples wrote in its own session. End this transaction so the reads below see it.
        db.commit()
        retriever.clear_vector_cache()
        company_ids = {slug: db.query(Company.id).filter_by(slug=slug).scalar() for slug in truth}
        for slug, company_id in company_ids.items():
            plant_public_document_probe(db, company_id, slug)
        if before_questions is not None:
            before_questions(db)

        probe_canaries = [canary for slug in truth for canary in _probe_canaries(slug).values()]
        all_canaries = canaries(truth) + probe_canaries
        markers = {slug: isolation_markers(truth, slug) for slug in truth}
        scored = []
        for question in questions:
            result = _ask(db, question, company_ids[question["company"]])
            scored.append(_score_question(question, result, truth, all_canaries, markers))
        probe_reachable, probes = public_document_probes(db, company_ids, all_canaries)

        recall, contradictions = contradiction_recall(db, truth)
        cost, partial = _actual_cost(db, start_id)
        config = get_config()
        covered = [s for s in scored if s["covered"]]
        uncovered = [s for s in scored if not s["covered"]]
        providers = {slot: f"{config.slot(slot).provider}/{config.slot(slot).model}" for slot in SLOTS}
        fixture = any(config.slot(name).provider == "fake" for name in ("reasoning", "bulk", "embedding"))
        report = {
            "permission_leak": sum(1 for s in scored if s["permission_leak"]) + sum(1 for p in probes if p["leaked"]),
            "public_document_probe_reachable": probe_reachable,
            "public_document_probes": probes,
            "company_isolation": sum(1 for s in scored if s["company_isolation"]),
            "citation_accuracy": _ratio(sum(1 for s in covered if s["citation_ok"]), len(covered)),
            "correct_refusal": _ratio(sum(1 for s in uncovered if s["refused_correctly"]), len(uncovered)),
            "contradiction_recall": recall,
            "questions": len(scored),
            "errors": sum(1 for s in scored if s["state"] == "error"),
            "provider": config.slot("reasoning").provider,
            "providers": providers,
            "cost_usd": cost,
            "cost_partial": partial,
            "estimated_cost_usd": est["total_usd"],
            "estimate_complete": est["complete"],
            "fixture_run": fixture,
            "note": FIXTURE_NOTE if fixture else "",
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "targets": {name: {"op": op, "value": value} for name, (op, value) in TARGETS.items()},
            "contradictions": contradictions,
            "results": scored,
        }
    finally:
        db.close()

    report["targets_met"] = {name: _meets(report[name], *TARGETS[name]) for name in TARGETS}
    if reports_dir is not None:
        paths = write_reports(report, Path(reports_dir))
        report["report_files"] = [str(p) for p in paths]
    return report


def _meets(actual, op: str, target) -> bool:
    return actual == target if op == "==" else actual >= target


# ---------------------------------------------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------------------------------------------

def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def render_markdown(report: dict) -> str:
    def row(label, key, shown, target):
        verdict = "met" if report["targets_met"][key] else "MISSED"
        return f"| {label} | {shown} | {target} | {verdict} |"

    cost = f"${report['cost_usd']:.4f}" + (" (partial: some calls have no known price)" if report["cost_partial"] else "")
    lines = [f"# Company Brain evaluation: {report['provider']}", ""]
    if report["fixture_run"]:
        lines += [f"> **Fixture run.** {FIXTURE_NOTE}", ""]
    lines += [
        f"- Created: {report['created_at']}",
        f"- Questions: {report['questions']} ({report['errors']} ended in an error)",
        "- Slots: " + ", ".join(f"{slot} {name}" for slot, name in report["providers"].items()),
        f"- Actual cost from ai_usage_logs: {cost}",
        "", "| Measure | Actual | Target | Result |", "| --- | --- | --- | --- |",
        row("Permission leaks", "permission_leak", report["permission_leak"], "0"),
        row("Company isolation breaches", "company_isolation", report["company_isolation"], "0"),
        row("Citation accuracy", "citation_accuracy", _pct(report["citation_accuracy"]), ">= 90%"),
        row("Correct refusal", "correct_refusal", _pct(report["correct_refusal"]), ">= 90%"),
        row("Contradiction recall", "contradiction_recall", _pct(report["contradiction_recall"]), ">= 80%"),
        "", "## Planted contradictions", "", "| Company | Topic | Found |", "| --- | --- | --- |",
    ]
    lines += [f"| {d['company']} | {d['topic']} | {'yes' if d['found'] else 'no'} |" for d in report["contradictions"]]
    lines += ["", "## Public document leak probes", "",
              f"A public document's chunk sources a confidential or rejected node. HR's search can reach it: "
              f"{'yes' if report['public_document_probe_reachable'] else 'NO, so these rows prove nothing'}.", "",
              "| Company | Audience | State | Leaked |", "| --- | --- | --- | --- |"]
    lines += [f"| {p['company']} | {p['audience']} | {p['state']} | {len(p['leaked'])} |"
              for p in report["public_document_probes"]]
    lines += ["", "## Questions", "", "| Id | Company | Lang | Audience | Covered | State | Citation | Leak | Isolation |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in report["results"]:
        citation = "-" if r["citation_ok"] is None else ("ok" if r["citation_ok"] else "miss")
        state = r["state"] if not r["error"] else f"error ({r['error']})"
        lines.append(
            f"| {r['id']} | {r['company']} | {r['language']} | {r['audience']} | {'yes' if r['covered'] else 'no'} | "
            f"{state} | {citation} | {len(r['permission_leak'])} | {len(r['company_isolation'])} |"
        )
    return "\n".join(lines) + "\n"


def write_reports(report: dict, directory: Path) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = directory / f"brain-{report['provider']}-{stamp}"
    markdown, data = base.with_suffix(".md"), base.with_suffix(".json")
    markdown.write_text(render_markdown(report), encoding="utf-8")
    data.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return [markdown, data]


# ---------------------------------------------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------------------------------------------

def make_confirm(yes: bool) -> Callable[[str, dict], bool]:
    def confirm(_text: str, est: dict) -> bool:
        if yes or (est["complete"] and est["total_usd"] == 0):
            return True
        if not sys.stdin.isatty():
            print("This run may spend money and no terminal is attached. Re-run with --yes to accept the estimate.")
            return False
        return input("Type 'yes' to spend up to the estimate above (or more if it is partial): ").strip().lower() == "yes"

    return confirm


def _prepare_environment(profile: str, workdir: Path) -> None:
    """Point the app at a throwaway database before any app module is imported."""
    os.environ["DATABASE_URL"] = f"sqlite:///{workdir / 'eval-brain.db'}"
    os.environ["STORAGE_DIR"] = str(workdir / "storage")
    os.environ["SECRET_KEY"] = secrets.token_urlsafe(32)
    os.environ["SAMPLE_USER_PASSWORD"] = secrets.token_urlsafe(16)  # Throwaway users in a throwaway database.
    os.environ.setdefault("APP_ENV", "development")
    if profile == "fake":
        for slot in SLOTS:
            os.environ[f"AI_{slot.upper()}_PROVIDER"] = "fake"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m eval.brain.run", description=__doc__.split("\n\n")[0])
    parser.add_argument("--yes", action="store_true", help="Accept the printed cost estimate without asking.")
    parser.add_argument("--dry-run", action="store_true", help="Print the estimate and stop. No AI call is made.")
    parser.add_argument("--profile", default="env", help="'env' uses the providers set in the environment. 'fake' forces the fake provider.")
    args = parser.parse_args(argv)

    workdir = Path(tempfile.mkdtemp(prefix="eval-brain-"))
    try:
        _prepare_environment(args.profile, workdir)
        from app.database.database import engine
        from app.database.migrate import run_migrations

        try:
            run_migrations()
            report = evaluate(args.profile, make_confirm(args.yes), args.dry_run)
        except Exception as exc:
            if type(exc).__name__ in {"AIConfigError", "EvalError"}:
                print(f"Cannot run: {exc}", file=sys.stderr)
                return 2
            raise
        finally:
            engine.dispose()
        if report is None:
            return 0 if args.dry_run else 1
        print(render_markdown(report))
        for path in report["report_files"]:
            print(f"Wrote {path}")
        return 0
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
