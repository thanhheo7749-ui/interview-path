"""Question-plan overlap report.

Builds the screening plan for the same CV at both sample companies' Backend Developer job and reports how much the
two plans overlap, with the two plans side by side. A plan that is the same for every company would mean the
interview ignores the company; the target is an overlap under 50%.

    python -m eval.plans.run [--yes] [--dry-run] [--profile fake|env]

The run always uses a throwaway SQLite file, never the app's configured database. It prints an estimated cost before
any AI call and needs --yes or a typed confirmation when it could spend money.

Under the fake provider the plans are the code's own templates, so the overlap measures how much the templates share.
It does not measure real questions: that needs real AI keys.
"""
import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import sys
import tempfile
import textwrap
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

PLANS_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = PLANS_DIR.parents[1]
REPORTS_DIR = BACKEND_ROOT / "eval" / "reports"

SLOTS = ("reasoning", "bulk", "embedding", "stt", "tts")
JOB_TITLE = "Backend Developer"
LANGUAGE = "en"
TARGET_OVERLAP = 0.5
COLUMN_WIDTH = 58

# One CV for both companies, so any difference between the plans comes from the company. Invented, no real person.
SHARED_CV = """Sample Candidate
Backend engineer

- Built a REST service used by 3 internal teams.
- Cut report generation time by 40 percent.
- Maintained 12 scheduled jobs on a shared cluster.
"""

# Assumptions behind the estimate. They are printed with it, so nobody mistakes them for measurements.
CV_ASSESS_INPUT_TOKENS = 1500
CV_ASSESS_OUTPUT_TOKENS = 400
PLAN_INPUT_TOKENS = 1200
PLAN_OUTPUT_TOKENS = 600

FIXTURE_NOTE = (
    "This run used the fake AI provider, so every question is the code's own template and the overlap measures how much "
    "the templates share. It does not measure real questions: that needs real AI keys."
)
KEYS_NOTE = "The real overlap, with the AI phrasing questions, needs real AI keys and has not been measured."


class PlanReportError(RuntimeError):
    pass


def normalise(text: str) -> str:
    """Lower case, no accents or punctuation, single spaces: two questions that differ only in form count as one."""
    folded = unicodedata.normalize("NFKC", text).casefold()
    words = re.findall(r"\w+", folded, flags=re.UNICODE)
    return " ".join(words)


def jaccard(left: list[str], right: list[str]) -> float:
    a, b = {normalise(q) for q in left}, {normalise(q) for q in right}
    union = a | b
    return len(a & b) / len(union) if union else 0.0


# ---------------------------------------------------------------------------------------------------------------
# Estimate
# ---------------------------------------------------------------------------------------------------------------

def estimate(companies: int, truth: dict, seeding: bool) -> dict:
    """Estimated cost, built from stated assumptions. `complete` is False when any price is unknown."""
    from app.ai.config import get_config
    from app.ai.types import Usage
    from app.ai.usage import estimate_cost
    from eval.brain import run as brain

    config = get_config()
    bulk, reasoning = config.slot("bulk"), config.slot("reasoning")
    lines = []
    if seeding:
        # Seeding the sample companies is the same work the Company Brain harness estimates; leave out its question lines.
        lines += [line for line in brain.estimate(0, truth, seeding=True)["lines"]
                  if not line["label"].startswith(("0 ", "public document leak probes"))]
    lines += [
        {"label": f"{companies} CV assessments", "slot": "bulk", "provider": bulk.provider, "model": bulk.model,
         "usage": Usage(input_tokens=companies * CV_ASSESS_INPUT_TOKENS, output_tokens=companies * CV_ASSESS_OUTPUT_TOKENS)},
        {"label": f"{companies} plan phrasings", "slot": "reasoning", "provider": reasoning.provider,
         "model": reasoning.model,
         "usage": Usage(input_tokens=companies * PLAN_INPUT_TOKENS, output_tokens=companies * PLAN_OUTPUT_TOKENS)},
    ]
    total, unpriced = 0.0, []
    for line in lines:
        cost = estimate_cost(line["model"], line["usage"])
        line["cost_usd"] = cost
        if cost is None:
            unpriced.append(line["label"])
        else:
            total += cost
    fixture = any(config.slot(name).provider == "fake" for name in ("reasoning", "bulk", "embedding"))
    return {"lines": lines, "total_usd": total, "complete": not unpriced, "unpriced": unpriced, "seeding": seeding,
            "fixture": fixture}


def format_estimate(est: dict) -> str:
    out = ["Estimated cost before any AI call (assumptions, not measurements):"]
    for line in est["lines"]:
        usage = line["usage"]
        price = "price unknown" if line["cost_usd"] is None else f"${line['cost_usd']:.4f}"
        out.append(f"  - {line['label']}: {line['provider']}/{line['model']} ({line['slot']}), "
                   f"{usage.input_tokens} input + {usage.output_tokens} output tokens, {price}")
    if not est["seeding"]:
        out.append("  - seeding skipped: the sample companies are already present.")
    if est["complete"]:
        out.append(f"  Total: ${est['total_usd']:.4f}")
    else:
        out.append(f"  Total: AT LEAST ${est['total_usd']:.4f}. PARTIAL: no price is known for "
                   f"{', '.join(est['unpriced'])}, so the real cost is higher than this figure.")
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
        raise PlanReportError(f"Unknown profile '{profile}'. Use 'fake' or 'env' (the providers set in the environment).")
    reset_config()


def _require_sqlite() -> None:
    from app.database.database import engine

    if engine.url.get_backend_name() != "sqlite":
        raise PlanReportError("The report only runs on a SQLite database. Run it through `python -m eval.plans.run`.")


def _seeded(db, slugs) -> bool:
    from app.database.sql_models import Company, Job

    for slug in slugs:
        company = db.query(Company).filter_by(slug=slug).first()
        if company is None or not db.query(Job.id).filter_by(company_id=company.id, title=JOB_TITLE).first():
            return False
    return True


def _plan_for(db, company, slug: str) -> dict:
    """Give the shared CV to a throwaway candidate at this company's Backend Developer job and build the plan."""
    from app.database.sql_models import Application, Job, User
    from app.hiring import planner, screening

    job = db.query(Job).filter_by(company_id=company.id, title=JOB_TITLE).order_by(Job.id).first()
    if job is None:
        raise PlanReportError(f"The sample company '{slug}' has no {JOB_TITLE} job.")
    user = User(email=f"plan-report-{slug}@example.test", full_name="Sample Candidate", hashed_password="!")
    db.add(user)
    db.flush()
    application = Application(
        company_id=company.id, job_id=job.id, job_version=job.version, alias="#E1", stage="invited",
        cv_text_blind=SHARED_CV, cv_blind_hash=hashlib.sha256(SHARED_CV.encode("utf-8")).hexdigest(),
        candidate_user_id=user.id, is_simulated=True,
    )
    db.add(application)
    db.flush()
    screening.assess(db, application)
    db.commit()
    plan = planner.build_plan(db, application, LANGUAGE)
    return {
        "company": slug, "job": job.title,
        "questions": [{"text": item.text, "source": item.source} for item in plan],
    }


def evaluate(profile: str = "env", confirm: Callable[[str, dict], bool] | None = None, dry_run: bool = False,
             reports_dir: Path | None = REPORTS_DIR) -> dict | None:
    """Returns the report, or None when it stopped before spending (dry run or declined)."""
    _require_sqlite()
    _apply_profile(profile)
    from app.ai.config import get_config
    from app.brain import seed
    from app.database.database import SessionLocal
    from app.database.sql_models import Company
    from eval.brain import run as brain

    truth = brain.load_truth()
    slugs = sorted(truth)
    db = SessionLocal()
    try:
        est = estimate(len(slugs), truth, seeding=not _seeded(db, slugs))
        print(format_estimate(est))
        if dry_run:
            print("Dry run: nothing was seeded and no AI call was made.")
            return None
        if confirm is None or not confirm(format_estimate(est), est):
            print("Not confirmed: no AI call was made.")
            return None

        seed.seed_samples(auto_approve=True)
        db.commit()  # seed_samples wrote in its own session; end this transaction so the reads below see it
        plans = [_plan_for(db, db.query(Company).filter_by(slug=slug).one(), slug) for slug in slugs]
        config = get_config()
        fixture = any(config.slot(name).provider == "fake" for name in ("reasoning", "bulk", "embedding"))
        texts = [[q["text"] for q in plan["questions"]] for plan in plans]
        overlap = jaccard(texts[0], texts[1])
        shared = sorted({normalise(q) for q in texts[0]} & {normalise(q) for q in texts[1]})
        report = {
            "job": JOB_TITLE, "language": LANGUAGE, "companies": slugs, "plans": plans,
            "overlap": overlap, "shared_questions": shared, "target": TARGET_OVERLAP,
            "target_met": overlap < TARGET_OVERLAP,
            "provider": config.slot("reasoning").provider,
            "providers": {slot: f"{config.slot(slot).provider}/{config.slot(slot).model}" for slot in SLOTS},
            "estimated_cost_usd": est["total_usd"], "fixture_run": fixture,
            "note": FIXTURE_NOTE if fixture else "",
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    finally:
        db.close()
    if reports_dir is not None:
        report["report_files"] = [str(p) for p in write_reports(report, Path(reports_dir))]
    return report


# ---------------------------------------------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------------------------------------------

def side_by_side(plans: list[dict], width: int = COLUMN_WIDTH) -> str:
    left, right = plans[0], plans[1]
    rows = [f"{left['company']:<{width}} | {right['company']}", f"{'-' * width}-+-{'-' * width}"]
    count = max(len(left["questions"]), len(right["questions"]))
    for index in range(count):
        a = textwrap.wrap(f"{index + 1}. {left['questions'][index]['text']}", width) if index < len(left["questions"]) else [""]
        b = textwrap.wrap(f"{index + 1}. {right['questions'][index]['text']}", width) if index < len(right["questions"]) else [""]
        for line in range(max(len(a), len(b))):
            rows.append(f"{(a[line] if line < len(a) else ''):<{width}} | {b[line] if line < len(b) else ''}")
        rows.append(f"{'':<{width}} |")
    return "\n".join(rows)


def render_text(report: dict) -> str:
    verdict = "met" if report["target_met"] else "MISSED"
    lines = [
        f"Question-plan overlap for the {report['job']} job at {' and '.join(report['companies'])}, same CV, language "
        f"{report['language']}",
        f"Jaccard overlap of normalised question text: {report['overlap'] * 100:.0f}% "
        f"(target: under {report['target'] * 100:.0f}%): {verdict}",
        "",
        side_by_side(report["plans"]),
        "",
        "Questions both plans share:" if report["shared_questions"] else "The plans share no question.",
    ]
    lines += [f"  - {q}" for q in report["shared_questions"]]
    lines += [""]
    if report["fixture_run"]:
        lines += [FIXTURE_NOTE, KEYS_NOTE]
    return "\n".join(lines) + "\n"


def render_markdown(report: dict) -> str:
    lines = [f"# Question-plan overlap: {report['provider']}", ""]
    if report["fixture_run"]:
        lines += [f"> **Fixture run.** {FIXTURE_NOTE}", ""]
    lines += [
        f"- Created: {report['created_at']}",
        f"- Job: {report['job']} at {', '.join(report['companies'])}; one shared CV; language {report['language']}",
        "- Slots: " + ", ".join(f"{slot} {name}" for slot, name in report["providers"].items()),
        f"- Overlap (Jaccard of normalised question text): **{report['overlap'] * 100:.0f}%**, target under "
        f"{report['target'] * 100:.0f}%: {'met' if report['target_met'] else 'MISSED'}",
        "", "## Plans side by side", "", "```", side_by_side(report["plans"]), "```", "",
    ]
    return "\n".join(lines) + "\n"


def write_reports(report: dict, directory: Path) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = directory / f"plans-{report['provider']}-{stamp}"
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
    os.environ["DATABASE_URL"] = f"sqlite:///{workdir / 'eval-plans.db'}"
    os.environ["STORAGE_DIR"] = str(workdir / "storage")
    os.environ["SECRET_KEY"] = secrets.token_urlsafe(32)
    os.environ["SAMPLE_USER_PASSWORD"] = secrets.token_urlsafe(16)  # Throwaway users in a throwaway database.
    os.environ.setdefault("APP_ENV", "development")
    if profile == "fake":
        for slot in SLOTS:
            os.environ[f"AI_{slot.upper()}_PROVIDER"] = "fake"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m eval.plans.run", description=__doc__.split("\n\n")[0])
    parser.add_argument("--yes", action="store_true", help="Accept the printed cost estimate without asking.")
    parser.add_argument("--dry-run", action="store_true", help="Print the estimate and stop. No AI call is made.")
    parser.add_argument("--profile", default="env", help="'env' uses the providers set in the environment. 'fake' forces the fake provider.")
    args = parser.parse_args(argv)

    workdir = Path(tempfile.mkdtemp(prefix="eval-plans-"))
    try:
        _prepare_environment(args.profile, workdir)
        from app.database.database import engine
        from app.database.migrate import run_migrations

        try:
            run_migrations()
            report = evaluate(args.profile, make_confirm(args.yes), args.dry_run)
        except Exception as exc:
            if type(exc).__name__ in {"AIConfigError", "PlanReportError"}:
                print(f"Cannot run: {exc}", file=sys.stderr)
                return 2
            raise
        finally:
            engine.dispose()
        if report is None:
            return 0 if args.dry_run else 1
        print(render_text(report))
        for path in report["report_files"]:
            print(f"Wrote {path}")
        return 0
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
