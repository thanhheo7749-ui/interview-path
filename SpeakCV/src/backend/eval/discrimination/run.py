"""Discrimination guard evaluation.

Runs every labelled statement in statements.yaml through the guard and reports precision and recall per language and
overall, twice: for the rules alone, and for the rules plus the AI classifier (the guard as the product runs it).

    python -m eval.discrimination.run [--yes] [--dry-run] [--profile fake|env]

The run always uses a throwaway SQLite file, never the app's configured database. It prints an estimated cost before
any AI call and needs --yes or a typed confirmation when it could spend money.
Under the fake provider the classifier never flags anything, so the figures describe the rules only.
"""
import argparse
import json
import os
import secrets
import shutil
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import yaml

EVAL_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = EVAL_DIR.parents[1]
STATEMENTS_PATH = EVAL_DIR / "statements.yaml"
REPORTS_DIR = BACKEND_ROOT / "eval" / "reports"

SLOTS = ("reasoning", "bulk", "embedding", "stt", "tts")
LANGUAGES = ("vi", "en", "ko")
TARGET_RECALL = 0.90

# Assumptions behind the estimate. They are printed with it, so nobody mistakes them for measurements.
CHARS_PER_TOKEN = 3
OUTPUT_TOKENS_PER_CHECK = 60

FIXTURE_NOTE = (
    "Fake provider: this measures the rules only, not the real classifier. The fake classifier never flags a "
    "statement, so the rules plus classifier figures equal the rules-only figures. Run with a real provider to "
    "measure the classifier."
)


class EvalError(RuntimeError):
    pass


def load_statements(path: Path = STATEMENTS_PATH) -> list[dict]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or []


# ---------------------------------------------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------------------------------------------

def _ratio(hits: int, total: int) -> float:
    """0.0 when there is nothing to divide by. The counts beside every figure show when that is the case."""
    return hits / total if total else 0.0


def score(rows: list[dict], key: str) -> dict:
    """Confusion counts, precision and recall for one prediction column (`key` holds True, False or "unchecked").

    An "unchecked" result (the classifier failed) is counted apart and is not a positive: nothing was found.
    """
    tp = sum(1 for r in rows if r["label"] and r[key] is True)
    fn = sum(1 for r in rows if r["label"] and r[key] is not True)
    fp = sum(1 for r in rows if not r["label"] and r[key] is True)
    tn = sum(1 for r in rows if not r["label"] and r[key] is not True)
    return {
        "total": len(rows), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "unchecked": sum(1 for r in rows if r[key] == "unchecked"),
        "precision": _ratio(tp, tp + fp), "recall": _ratio(tp, tp + fn),
    }


def summarise(rows: list[dict]) -> dict:
    """Per language and overall scores for the rules alone and for the rules plus the classifier."""
    out = {}
    for mode, key in (("rules", "rules_flagged"), ("combined", "combined_flagged")):
        out[mode] = {"overall": score(rows, key)}
        for language in sorted({r["language"] for r in rows}, key=lambda l: LANGUAGES.index(l) if l in LANGUAGES else 99):
            out[mode][language] = score([r for r in rows if r["language"] == language], key)
    return out


def judge(statement: dict, company_id: int | None = None) -> dict:
    """Run one statement through the rules, then through the whole guard."""
    from app.bridges import discrimination

    text = statement["text"]
    by_rules = discrimination.check_rules(text)
    result = discrimination.check(text, company_id)  # Reruns the rules, which is free, then asks the classifier.
    if result is None:
        combined = False
    elif result.unchecked:
        combined = "unchecked"
    else:
        combined = True
    return {
        "text": text, "language": statement["language"], "label": bool(statement["label"]),
        "category": statement.get("category", "none"),
        "rules_flagged": by_rules is not None, "rules_category": by_rules.category if by_rules else None,
        "combined_flagged": combined, "combined_category": result.category if result and not result.unchecked else None,
    }


# ---------------------------------------------------------------------------------------------------------------
# Estimate
# ---------------------------------------------------------------------------------------------------------------

def estimate(statements: list[dict]) -> dict:
    """Estimated cost. Only statements the rules do not catch reach the classifier."""
    from app.ai.config import get_config
    from app.ai.types import Usage
    from app.ai.usage import estimate_cost
    from app.bridges import discrimination

    slot = get_config().slot("bulk")
    reaching = [s for s in statements if discrimination.check_rules(s["text"]) is None]
    prompt_chars = len(discrimination.SYSTEM) * len(reaching) + sum(len(s["text"]) for s in reaching)
    usage = Usage(input_tokens=-(-prompt_chars // CHARS_PER_TOKEN), output_tokens=OUTPUT_TOKENS_PER_CHECK * len(reaching))
    cost = estimate_cost(slot.model, usage)
    return {
        "statements": len(statements), "classifier_calls": len(reaching), "slot": "bulk", "provider": slot.provider,
        "model": slot.model, "usage": usage, "cost_usd": cost, "total_usd": cost or 0.0, "complete": cost is not None,
        "fixture": slot.provider == "fake",
    }


def format_estimate(est: dict) -> str:
    usage = est["usage"]
    price = "price unknown" if est["cost_usd"] is None else f"${est['cost_usd']:.4f}"
    out = [
        "Estimated cost before any AI call (assumptions, not measurements):",
        f"  - {est['classifier_calls']} classifier calls out of {est['statements']} statements (the rest are caught by "
        f"the rules): {est['provider']}/{est['model']} ({est['slot']}), {usage.input_tokens} input + "
        f"{usage.output_tokens} output tokens, {price}",
        f"  Assumes ~{CHARS_PER_TOKEN} characters per token and {OUTPUT_TOKENS_PER_CHECK} output tokens per call.",
    ]
    if est["complete"]:
        out.append(f"  Total: ${est['total_usd']:.4f}")
    else:
        out.append(f"  Total: PARTIAL: no price is known for {est['model']}, so the real cost is unknown.")
    if est["fixture"]:
        out.append("  Fake provider in use: no money is spent.")
    return "\n".join(out)


# ---------------------------------------------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------------------------------------------

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
        raise EvalError("The harness only runs on a SQLite database. Run it through `python -m eval.discrimination.run`.")


def evaluate(profile: str = "env", confirm: Callable[[str, dict], bool] | None = None, dry_run: bool = False,
             reports_dir: Path | None = REPORTS_DIR, statements: list[dict] | None = None) -> dict | None:
    """Run the evaluation. Returns the report dictionary, or None when it stopped before spending (dry run or declined)."""
    _require_sqlite()
    _apply_profile(profile)
    from app.ai.config import get_config

    statements = load_statements() if statements is None else statements
    est = estimate(statements)
    print(format_estimate(est))
    if dry_run:
        print("Dry run: no AI call was made.")
        return None
    if confirm is None or not confirm(format_estimate(est), est):
        print("Not confirmed: no AI call was made.")
        return None

    rows = [judge(s) for s in statements]
    summary = summarise(rows)
    config = get_config()
    provider = config.slot("bulk").provider
    fixture = provider == "fake"
    overall = summary["combined"]["overall"]
    report = {
        "provider": provider, "model": config.slot("bulk").model, "fixture_run": fixture,
        "note": FIXTURE_NOTE if fixture else "",
        "statements": len(rows), "rule_hits": sum(1 for r in rows if r["rules_flagged"]),
        "classifier_calls": est["classifier_calls"], "estimated_cost_usd": est["total_usd"],
        "estimate_complete": est["complete"],
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target_recall": TARGET_RECALL, "summary": summary,
        "precision": overall["precision"], "recall": overall["recall"],
        "rules_precision": summary["rules"]["overall"]["precision"], "rules_recall": summary["rules"]["overall"]["recall"],
        "per_language": {
            language: {"precision": summary["combined"][language]["precision"], "recall": summary["combined"][language]["recall"],
                       "rules_precision": summary["rules"][language]["precision"],
                       "rules_recall": summary["rules"][language]["recall"]}
            for language in summary["combined"] if language != "overall"
        },
        "category_hits": dict(Counter(r["combined_category"] for r in rows if r["combined_flagged"] is True and r["label"])),
        "results": rows,
    }
    report["target_met"] = {"combined": overall["recall"] >= TARGET_RECALL,
                            "rules": summary["rules"]["overall"]["recall"] >= TARGET_RECALL}
    if reports_dir is not None:
        report["report_files"] = [str(p) for p in write_reports(report, Path(reports_dir))]
    return report


# ---------------------------------------------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------------------------------------------

def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def _table(block: dict) -> list[str]:
    lines = ["| Language | Statements | TP | FP | FN | TN | Precision | Recall |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for name, s in block.items():
        unchecked = f" ({s['unchecked']} unchecked)" if s["unchecked"] else ""
        lines.append(f"| {name}{unchecked} | {s['total']} | {s['tp']} | {s['fp']} | {s['fn']} | {s['tn']} | "
                     f"{_pct(s['precision'])} | {_pct(s['recall'])} |")
    return lines


def render_markdown(report: dict) -> str:
    lines = [f"# Discrimination guard evaluation: {report['provider']}", ""]
    if report["fixture_run"]:
        lines += [f"> **Rules only.** {report['note']}", ""]
    lines += [
        f"- Created: {report['created_at']}",
        f"- Statements: {report['statements']}, of which {report['rule_hits']} were flagged by the rules and "
        f"{report['classifier_calls']} went on to the classifier",
        f"- Classifier slot: {report['provider']}/{report['model']}",
        f"- Target: recall of at least {_pct(report['target_recall'])} overall. "
        f"Rules alone: {'met' if report['target_met']['rules'] else 'MISSED'}. "
        f"Rules plus classifier: {'met' if report['target_met']['combined'] else 'MISSED'}"
        + (" (fake classifier, so not a real measurement)." if report["fixture_run"] else "."),
        "", "## Rules alone", "", *_table(report["summary"]["rules"]),
        "", "## Rules plus classifier", "", *_table(report["summary"]["combined"]),
    ]
    missed = [r for r in report["results"] if r["label"] and r["combined_flagged"] is not True]
    wrong = [r for r in report["results"] if not r["label"] and r["combined_flagged"] is True]
    lines += ["", "## Missed discrimination (false negatives, rules plus classifier)", ""]
    lines += [f"- [{r['language']}/{r['category']}] {r['text']}" for r in missed] or ["- none"]
    lines += ["", "## Wrongly flagged job-related text (false positives, rules plus classifier)", ""]
    lines += [f"- [{r['language']}] {r['text']} (flagged as {r['combined_category']})" for r in wrong] or ["- none"]
    return "\n".join(lines) + "\n"


def write_reports(report: dict, directory: Path) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = directory / f"discrimination-{report['provider']}-{stamp}"
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
    os.environ["DATABASE_URL"] = f"sqlite:///{workdir / 'eval-discrimination.db'}"
    os.environ["STORAGE_DIR"] = str(workdir / "storage")
    os.environ["SECRET_KEY"] = secrets.token_urlsafe(32)
    os.environ.setdefault("APP_ENV", "development")
    if profile == "fake":
        for slot in SLOTS:
            os.environ[f"AI_{slot.upper()}_PROVIDER"] = "fake"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m eval.discrimination.run", description=__doc__.split("\n\n")[0])
    parser.add_argument("--yes", action="store_true", help="Accept the printed cost estimate without asking.")
    parser.add_argument("--dry-run", action="store_true", help="Print the estimate and stop. No AI call is made.")
    parser.add_argument("--profile", default="env", help="'env' uses the providers set in the environment. 'fake' forces the fake provider.")
    args = parser.parse_args(argv)

    workdir = Path(tempfile.mkdtemp(prefix="eval-discrimination-"))
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
