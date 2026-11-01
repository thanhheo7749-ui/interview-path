"""Speech-to-text benchmark on the team's own clips.

    python -m eval.stt.run [--manifest PATH] [--yes] [--dry-run] [--profile fake|env]

The team records 10 to 15 short clips of accented Vietnamese and Korean speech (see README.md), lists them in
clips/manifest.yaml with the exact words spoken, and runs `make eval-stt`. The tool sends each clip to the
configured speech-to-text slot, then reports the character error rate (CER) and the average latency per language.

It invents no audio and no result. Under the fake provider the "transcript" is just the clip's own bytes read as
text, so the numbers measure nothing about real speech and the report says so.
"""
import argparse
import json
import mimetypes
import os
import secrets
import shutil
import sys
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import yaml

STT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = STT_DIR.parents[1]
MANIFEST_PATH = STT_DIR / "clips" / "manifest.yaml"
REPORTS_DIR = BACKEND_ROOT / "eval" / "reports"
FEATURE = "stt_benchmark"
GATE_CER = 0.15
SLOTS = ("reasoning", "bulk", "embedding", "stt", "tts")

# Assumption for the estimate only: ~48 kbps compressed speech (typical browser recording). A clip may set `seconds`.
ASSUMED_BYTES_PER_SECOND = 6000
NO_MONEY_LINE = "Fake provider in use: no money is spent and the result measures nothing."

FIXTURE_NOTE = (
    "This run used the fake speech-to-text provider. It measures no real speech: the fake provider returns the "
    "clip's own bytes as text. Record real clips and run with a real provider before reading any number here."
)
MISSING_MANIFEST_HELP = (
    "No clip manifest found at {path}. Record 10 to 15 clips of accented Vietnamese and Korean speech, "
    "write what was said for each in a manifest.yaml, and follow eval/stt/README.md."
)


def _normalise(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text).casefold()
    return "".join(ch for ch in folded if unicodedata.category(ch)[0] not in ("P", "Z") and not ch.isspace())


def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def _edits(reference: str, hypothesis: str) -> tuple[int, int]:
    ref, hyp = _normalise(reference), _normalise(hypothesis)
    return _levenshtein(ref, hyp), len(ref)


def character_error_rate(reference: str, hypothesis: str) -> float:
    """Edit distance over the reference length, ignoring case, spacing and punctuation."""
    distance, length = _edits(reference, hypothesis)
    if length == 0:
        return 0.0 if distance == 0 else 1.0
    return distance / length


def load_manifest(path: Path) -> list[dict]:
    path = Path(path)
    if not path.is_file():
        raise SystemExit(MISSING_MANIFEST_HELP.format(path=path))
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    clips = data.get("clips") if isinstance(data, dict) else None
    if not clips:
        raise SystemExit(f"The manifest {path} lists no clips. Add 10 to 15 under `clips:` as README.md describes.")
    loaded = []
    for index, clip in enumerate(clips, 1):
        missing = [key for key in ("file", "language", "reference") if not str(clip.get(key, "")).strip()]
        if missing:
            raise SystemExit(f"Clip {index} in the manifest {path} lacks: {', '.join(missing)}.")
        audio_path = path.parent / clip["file"]
        if not audio_path.is_file():
            raise SystemExit(f"Clip file {clip['file']} listed in the manifest {path} was not found at {audio_path}.")
        loaded.append({**clip, "path": audio_path})
    return loaded


def _mime(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or {".webm": "audio/webm"}.get(path.suffix.lower(), "application/octet-stream")


def _estimated_seconds(clip: dict) -> float:
    if clip.get("seconds"):
        return float(clip["seconds"])
    return clip["path"].stat().st_size / ASSUMED_BYTES_PER_SECOND


def estimate(clips: list[dict]) -> dict:
    from app.ai.config import get_config
    from app.ai.types import Usage
    from app.ai.usage import estimate_cost

    slot = get_config().slot("stt")
    seconds = sum(_estimated_seconds(clip) for clip in clips)
    cost = estimate_cost(slot.model, Usage(audio_seconds=seconds))
    return {"clips": len(clips), "seconds": seconds, "provider": slot.provider, "model": slot.model,
            "cost_usd": cost, "fixture": slot.provider == "fake"}


def format_estimate(est: dict) -> str:
    price = "price unknown, the real cost may be higher" if est["cost_usd"] is None else f"${est['cost_usd']:.4f}"
    lines = [
        f"Speech-to-text benchmark: {est['clips']} clips, about {est['seconds']:.0f} seconds of audio, "
        f"{est['provider']}/{est['model']}.",
        f"Estimated cost: {price} (assumes ~{ASSUMED_BYTES_PER_SECOND} bytes per second unless a clip sets `seconds`).",
    ]
    if est["fixture"]:
        lines.append(NO_MONEY_LINE)
    return "\n".join(lines)


def evaluate(manifest_path: Path, confirm: Callable[[str], bool] | None = None,
             reports_dir: Path | None = REPORTS_DIR) -> dict | None:
    """Transcribe every clip and score it. Returns None when the run was declined before any call."""
    from app.ai import gateway
    from app.ai.config import get_config

    clips = load_manifest(manifest_path)
    est = estimate(clips)
    text = format_estimate(est)
    print(text)
    if confirm is None or not confirm(text):
        print("Not confirmed: no AI call was made.")
        return None

    per_language: dict[str, dict] = {}
    results = []
    for clip in clips:
        language = str(clip["language"]).strip()
        error = None
        hypothesis, latency_ms = "", 0
        try:
            result = gateway.transcribe(clip["path"].read_bytes(), _mime(clip["path"]), [language], FEATURE)
            hypothesis, latency_ms = result.text, result.latency_ms
        except Exception as exc:  # A failed clip counts as fully wrong; it must not hide in the average.
            error = f"{type(exc).__name__}: {exc}"
        distance, length = _edits(clip["reference"], hypothesis)
        bucket = per_language.setdefault(language, {"distance": 0, "length": 0, "latencies": [], "clips": 0, "errors": 0})
        if error:
            distance, bucket["errors"] = max(length, 1), bucket["errors"] + 1
        else:
            bucket["latencies"].append(latency_ms)
        bucket["distance"] += distance
        bucket["length"] += length
        bucket["clips"] += 1
        results.append({
            "file": clip["file"], "language": language, "reference": clip["reference"], "hypothesis": hypothesis,
            "cer": 1.0 if error else character_error_rate(clip["reference"], hypothesis),
            "latency_ms": latency_ms, "error": error,
        })

    languages = {}
    for language, b in sorted(per_language.items()):
        cer = (b["distance"] / b["length"]) if b["length"] else (0.0 if b["distance"] == 0 else 1.0)
        latencies = b["latencies"]
        languages[language] = {
            "cer": cer, "gate_passed": cer <= GATE_CER, "clips": b["clips"], "errors": b["errors"],
            "avg_latency_ms": (sum(latencies) / len(latencies)) if latencies else 0,
        }
    slot = get_config().slot("stt")
    fixture = slot.provider == "fake"
    report = {
        "provider": slot.provider, "model": slot.model, "gate_cer": GATE_CER,
        "languages": languages, "gate_passed": all(v["gate_passed"] for v in languages.values()),
        "clips": len(results), "estimated_cost_usd": est["cost_usd"], "fixture_run": fixture,
        "note": FIXTURE_NOTE if fixture else "",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "results": results,
    }
    if reports_dir is not None:
        report["report_files"] = [str(p) for p in write_reports(report, Path(reports_dir))]
    return report


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def render_markdown(report: dict) -> str:
    lines = [f"# Speech-to-text benchmark: {report['provider']}/{report['model']}", ""]
    if report["fixture_run"]:
        lines += [f"> **Fixture run, measures no real speech.** {FIXTURE_NOTE}", ""]
    verdict = "PASSED" if report["gate_passed"] else "NOT PASSED: stop and consult the owner"
    lines += [
        f"- Created: {report['created_at']}", f"- Clips: {report['clips']}",
        f"- Gate: CER at or below {_pct(report['gate_cer'])} per language: {verdict}",
        "", "| Language | Clips | Errors | CER | Avg latency ms | Gate |", "| --- | --- | --- | --- | --- | --- |",
    ]
    for language, v in report["languages"].items():
        lines.append(f"| {language} | {v['clips']} | {v['errors']} | {_pct(v['cer'])} | {v['avg_latency_ms']:.0f} | "
                     f"{'met' if v['gate_passed'] else 'MISSED'} |")
    lines += ["", "## Clips", "", "| File | Lang | CER | Latency ms | Error |", "| --- | --- | --- | --- | --- |"]
    lines += [f"| {r['file']} | {r['language']} | {_pct(r['cer'])} | {r['latency_ms']} | {r['error'] or '-'} |"
              for r in report["results"]]
    return "\n".join(lines) + "\n"


def write_reports(report: dict, directory: Path) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = directory / f"stt-{report['provider']}-{stamp}"
    markdown, data = base.with_suffix(".md"), base.with_suffix(".json")
    markdown.write_text(render_markdown(report), encoding="utf-8")
    data.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return [markdown, data]


def make_confirm(yes: bool) -> Callable[[str], bool]:
    def confirm(text: str) -> bool:
        if yes or NO_MONEY_LINE in text:
            return True
        if not sys.stdin.isatty():
            print("This run may spend money and no terminal is attached. Re-run with --yes to accept the estimate.")
            return False
        return input("Type 'yes' to spend up to the estimate above (or more if the price is unknown): ").strip().lower() == "yes"

    return confirm


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m eval.stt.run", description=__doc__.split("\n\n")[0])
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--yes", action="store_true", help="Accept the printed cost estimate without asking.")
    parser.add_argument("--dry-run", action="store_true", help="Print the estimate and stop. No AI call is made.")
    parser.add_argument("--profile", default="env", help="'env' uses the providers set in the environment. 'fake' forces the fake provider.")
    args = parser.parse_args(argv)
    if args.profile not in ("env", "fake"):
        print("Unknown profile. Use 'fake' or 'env'.", file=sys.stderr)
        return 2

    # Usage rows go to a throwaway database so the benchmark never touches the app's data.
    workdir = Path(tempfile.mkdtemp(prefix="eval-stt-"))
    try:
        os.environ["DATABASE_URL"] = f"sqlite:///{workdir / 'eval-stt.db'}"
        os.environ["SECRET_KEY"] = secrets.token_urlsafe(32)
        os.environ.setdefault("APP_ENV", "development")
        if args.profile == "fake":
            for slot in SLOTS:
                os.environ[f"AI_{slot.upper()}_PROVIDER"] = "fake"
        from app.database import sql_models  # noqa: F401
        from app.database.database import Base, engine

        Base.metadata.create_all(bind=engine)
        try:
            if args.dry_run:
                print(format_estimate(estimate(load_manifest(args.manifest))))
                print("Dry run: no AI call was made.")
                return 0
            report = evaluate(args.manifest, make_confirm(args.yes))
        except Exception as exc:
            if type(exc).__name__ == "AIConfigError":
                print(f"Cannot run: {exc}", file=sys.stderr)
                return 2
            raise
        finally:
            engine.dispose()
        if report is None:
            return 1
        print(render_markdown(report))
        for path in report["report_files"]:
            print(f"Wrote {path}")
        return 0
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
