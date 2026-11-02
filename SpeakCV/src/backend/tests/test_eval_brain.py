import json
from collections import Counter

import pytest
import yaml

from app.ai.types import AIProviderError
from app.database.sql_models import AIUsageLog, Company, KbNode
from eval.brain import run

REQUIRED_FLOATS = ("citation_accuracy", "correct_refusal", "contradiction_recall")
VISIBLE = {"candidate": {"public"}, "employee": {"public", "internal"}}


def _evaluate(tmp_path, **kwargs):
    return run.evaluate(profile="fake", confirm=lambda *_: True, reports_dir=tmp_path, **kwargs)


def test_report_has_the_expected_keys_and_types(tmp_path):
    report = _evaluate(tmp_path)

    assert isinstance(report["permission_leak"], int)
    assert isinstance(report["company_isolation"], int)
    for key in REQUIRED_FLOATS:
        assert isinstance(report[key], float) and 0 <= report[key] <= 1, key
    assert report["questions"] == 30
    assert report["provider"] == "fake"
    assert isinstance(report["cost_usd"], float)
    assert report["created_at"]
    assert report["errors"] == 0


def test_no_leak_and_no_isolation_breach_under_fake_ai(tmp_path):
    report = _evaluate(tmp_path)

    assert report["permission_leak"] == 0
    assert report["company_isolation"] == 0


def test_fake_run_says_its_numbers_come_from_fixtures(tmp_path):
    report = _evaluate(tmp_path)

    assert report["fixture_run"] is True
    markdown = run.render_markdown(report)
    assert "do not measure real AI quality" in markdown
    assert "do not measure real AI quality" in report["note"]


def test_reports_are_written_as_markdown_and_json(tmp_path):
    report = _evaluate(tmp_path)

    names = sorted(p.name for p in tmp_path.iterdir())
    assert len(names) == 2
    assert names[0].startswith("brain-fake-") and names[0].endswith(".json")
    assert names[1].startswith("brain-fake-") and names[1].endswith(".md")
    assert json.loads((tmp_path / names[0]).read_text(encoding="utf-8"))["questions"] == 30
    assert "| Permission leaks |" in (tmp_path / names[1]).read_text(encoding="utf-8")
    assert len(report["report_files"]) == 2


def test_question_set_meets_the_agreed_counts():
    questions = run.load_questions()

    assert len(questions) == 30
    assert len({q["id"] for q in questions}) == 30
    assert Counter(q["language"] for q in questions) == {"vi": 10, "en": 10, "ko": 10}
    assert sum(q["covered"] for q in questions) == 20
    assert sum(not q["covered"] for q in questions) == 10
    assert sum(q.get("probe") == "other_company" for q in questions) >= 4
    for audience in ("candidate", "employee"):
        assert any(q.get("probe") == "confidential" and q["audience"] == audience for q in questions)
    assert {q["company"] for q in questions} == {"daehan-precision", "sori-labs"}
    assert {q["audience"] for q in questions} <= set(VISIBLE)


def test_every_expected_quote_is_verbatim_in_a_document_the_audience_may_read():
    from app.brain.text import quote_in

    truth_root = run.SAMPLES_DIR
    for q in run.load_questions():
        if not q["covered"]:
            assert "expected_quote" not in q
            continue
        spec = yaml.safe_load((truth_root / q["company"] / "company.yaml").read_text(encoding="utf-8"))
        readable = [
            (truth_root / q["company"] / d["file"]).read_text(encoding="utf-8")
            for d in spec["documents"] if d.get("visibility", "internal") in VISIBLE[q["audience"]]
        ]
        assert any(quote_in(q["expected_quote"], text) for text in readable), q["id"]


def test_dry_run_prints_an_estimate_and_makes_no_ai_call(db, tmp_path, capsys):
    result = run.evaluate(profile="fake", confirm=lambda *_: pytest.fail("a dry run must not ask"), dry_run=True,
                          reports_dir=tmp_path)

    assert result is None
    assert "Estimated cost" in capsys.readouterr().out
    assert db.query(AIUsageLog).count() == 0
    assert db.query(Company).count() == 0
    assert list(tmp_path.iterdir()) == []


def test_a_declined_confirmation_makes_no_ai_call(db, tmp_path):
    assert run.evaluate(profile="fake", confirm=lambda *_: False, reports_dir=tmp_path) is None
    assert db.query(AIUsageLog).count() == 0
    assert db.query(Company).count() == 0
    assert list(tmp_path.iterdir()) == []


def test_the_estimate_is_printed_before_confirmation_is_asked(tmp_path, capsys):
    seen = []

    def confirm(text, est):
        seen.append(capsys.readouterr().out)
        return False

    run.evaluate(profile="fake", confirm=confirm, reports_dir=tmp_path)

    assert "Estimated cost" in seen[0]


def test_an_unpriced_model_makes_the_estimate_say_it_is_partial(monkeypatch):
    monkeypatch.setattr("app.ai.usage.estimate_cost", lambda model, usage: None)
    from app.ai.config import reset_config

    reset_config()
    est = run.estimate(30, run.load_truth(), seeding=True)

    assert est["complete"] is False
    assert est["unpriced"]
    assert "PARTIAL" in run.format_estimate(est)


def test_a_complete_estimate_does_not_claim_to_be_partial():
    est = run.estimate(30, run.load_truth(), seeding=False)

    assert est["complete"] is True
    assert "PARTIAL" not in run.format_estimate(est)


def test_an_unconfirmed_run_that_could_spend_needs_yes(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    paid = {"complete": True, "total_usd": 0.5}
    partial = {"complete": False, "total_usd": 0.0}
    free = {"complete": True, "total_usd": 0.0}

    assert run.make_confirm(False)("", free) is True
    assert run.make_confirm(False)("", paid) is False
    assert run.make_confirm(False)("", partial) is False
    assert run.make_confirm(True)("", paid) is True


def test_a_canary_in_a_candidate_visible_node_is_counted_as_a_leak(tmp_path):
    planted = "CANARY-SORI-LABS-SALARY-7741"

    def plant(db):
        company_id = db.query(Company.id).filter_by(slug="sori-labs").scalar()
        nodes = db.query(KbNode).filter_by(company_id=company_id, status="published", visibility="public").all()
        assert nodes
        for node in nodes:
            node.body = f"{node.body} {planted}"
        db.commit()

    report = _evaluate(tmp_path, before_questions=plant)

    assert report["permission_leak"] > 0
    leaked = [r for r in report["results"] if r["permission_leak"]]
    assert all(r["audience"] in ("candidate", "employee") for r in leaked)
    assert planted in leaked[0]["permission_leak"]


def test_public_document_probes_reach_a_real_chunk_and_find_no_leak(tmp_path):
    report = _evaluate(tmp_path)

    assert report["public_document_probe_reachable"] is True
    probes = report["public_document_probes"]
    assert len(probes) == 4
    assert {(p["company"], p["audience"]) for p in probes} == {
        (slug, kind) for slug in ("sori-labs", "daehan-precision") for kind in ("candidate", "employee")
    }
    assert all(p["leaked"] == [] for p in probes)
    assert report["questions"] == 30


def test_the_leak_check_catches_a_chunk_filter_that_only_looks_at_the_document(tmp_path, monkeypatch):
    from sqlalchemy import and_

    from app.brain import audience as aud
    from app.database.sql_models import KbChunk

    monkeypatch.setattr(aud, "chunk_filter", lambda a: and_(KbChunk.company_id == a.company_id, aud.document_filter(a)))
    report = _evaluate(tmp_path)

    probes = report["public_document_probes"]
    assert report["permission_leak"] == (sum(1 for r in report["results"] if r["permission_leak"])
                                         + sum(1 for p in probes if p["leaked"])) > 0
    assert all(p["leaked"] for p in probes)
    leaked = [canary for probe in probes for canary in probe["leaked"]]
    assert any("CONFIDENTIAL" in canary for canary in leaked)
    assert any("REJECTED" in canary for canary in leaked)


def test_the_leak_check_catches_a_straddling_quote_linked_only_where_it_is_whole(tmp_path, monkeypatch):
    from app.brain import ingestion
    from app.brain.text import quote_in

    monkeypatch.setattr(ingestion, "chunks_sharing_quote",
                        lambda quote, chunks: [i for i, text in enumerate(chunks) if quote_in(quote, text)])
    report = _evaluate(tmp_path)

    leaked = [canary for probe in report["public_document_probes"] for canary in probe["leaked"]]
    assert any("STRADDLING" in canary for canary in leaked)
    assert report["permission_leak"] > 0


def test_isolation_check_flags_text_that_only_the_other_company_holds():
    truth = run.load_truth()
    markers = run.isolation_markers(truth, "daehan-precision")

    assert "CANARY-SORI-LABS-SALARY-7741" in markers
    assert "FastAPI or a similar async web framework" in markers
    assert "CANARY-DAEHAN-PRECISION-SALARY-7741" not in markers
    assert run.contains_any("context: ... FastAPI or a similar async web framework ...", markers)
    assert not run.contains_any("Java development experience of at least 3 years", markers)


def test_a_failed_ai_call_is_an_error_for_that_question_not_the_end_of_the_run(tmp_path, monkeypatch):
    from app.brain import copilot

    real_ask = copilot.ask
    calls = {"n": 0}

    def flaky(db, audience, question, user_id):
        calls["n"] += 1
        if calls["n"] % 2 == 0:
            raise AIProviderError("simulated vendor failure")
        return real_ask(db, audience, question, user_id)

    monkeypatch.setattr(copilot, "ask", flaky)
    report = _evaluate(tmp_path)

    assert report["questions"] == 30
    assert report["errors"] == 15
    assert sum(r["state"] == "error" for r in report["results"]) == 15


def test_prompt_capture_records_system_and_messages_and_restores_the_gateway():
    from app.ai import gateway

    before = gateway.generate_text
    with run.capture_prompts() as captured:
        gateway.generate_text("reasoning", "SYSTEM-TEXT", [{"role": "user", "content": "USER-TEXT"}], 20, "eval_probe")
    assert "SYSTEM-TEXT" in captured[0] and "USER-TEXT" in captured[0]
    assert gateway.generate_text is before
