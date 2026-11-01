import json
from collections import Counter

import pytest

from app.ai.providers import fake
from app.bridges import discrimination
from eval.discrimination import run

LANGUAGES = ("vi", "en", "ko")


def _evaluate(tmp_path, **kwargs):
    return run.evaluate(profile="fake", confirm=lambda *_: True, reports_dir=tmp_path, **kwargs)


def test_statement_set_meets_the_counts():
    statements = run.load_statements()

    assert len(statements) >= 60
    for language in LANGUAGES:
        mine = [s for s in statements if s["language"] == language]
        assert len(mine) >= 20, language
        positives = sum(1 for s in mine if s["label"])
        assert abs(positives - (len(mine) - positives)) <= 2, language
    assert {s["language"] for s in statements} == set(LANGUAGES)
    assert all(isinstance(s["label"], bool) and s["text"].strip() for s in statements)
    categories = {s["category"] for s in statements if s["label"]}
    assert categories == set(discrimination.CATEGORIES)
    assert all(s["category"] == "none" for s in statements if not s["label"])
    assert len({s["text"] for s in statements}) == len(statements)


def test_fake_run_returns_float_precision_and_recall_per_language(tmp_path):
    report = _evaluate(tmp_path)

    for mode in ("rules", "combined"):
        for name in (*LANGUAGES, "overall"):
            block = report["summary"][mode][name]
            assert isinstance(block["precision"], float) and 0 <= block["precision"] <= 1
            assert isinstance(block["recall"], float) and 0 <= block["recall"] <= 1
    assert set(report["per_language"]) == set(LANGUAGES)
    assert report["statements"] == len(run.load_statements())
    assert report["rule_hits"] == sum(1 for r in report["results"] if r["rules_flagged"])
    assert report["rule_hits"] > 0


def test_fake_run_measures_rules_only_and_says_so(tmp_path):
    report = _evaluate(tmp_path)

    assert report["fixture_run"] is True
    assert report["summary"]["rules"] == report["summary"]["combined"]
    markdown = run.render_markdown(report)
    assert "measures the rules only, not the real classifier" in markdown
    assert report["report_files"]
    written = json.loads(open(report["report_files"][1], encoding="utf-8").read())
    assert written["recall"] == report["recall"]


def test_declined_confirmation_makes_no_call(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(discrimination.gateway, "generate_structured", lambda *a, **k: calls.append(a))

    report = run.evaluate(profile="fake", confirm=lambda *_: False, reports_dir=tmp_path)

    assert report is None and calls == [] and not list(tmp_path.iterdir())


def test_dry_run_makes_no_call(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(discrimination.gateway, "generate_structured", lambda *a, **k: calls.append(a))

    assert run.evaluate(profile="fake", dry_run=True, confirm=lambda *_: True, reports_dir=tmp_path) is None
    assert calls == []


def test_estimate_counts_only_statements_that_reach_the_classifier(tmp_path):
    statements = [{"text": "Must be male", "language": "en", "label": True, "category": "gender"},
                  {"text": "Knows Kubernetes", "language": "en", "label": False, "category": "none"}]
    run._apply_profile("fake")

    est = run.estimate(statements)

    assert est["classifier_calls"] == 1 and est["fixture"] is True


def test_precision_and_recall_on_a_tiny_injected_list(tmp_path):
    fake.reset()
    # Rules catch "Must be male" (true positive) and "Preferably under 30" (true positive) and, wrongly,
    # "Built software for Catholic schools" (false positive). They miss "Young dynamic team member" (false negative).
    # "Knows Kubernetes" is a true negative. The Vietnamese pair is one true positive and one false negative.
    statements = [
        {"text": "Must be male", "language": "en", "label": True, "category": "gender"},
        {"text": "Preferably under 30", "language": "en", "label": True, "category": "age"},
        {"text": "Built software for Catholic schools", "language": "en", "label": False, "category": "none"},
        {"text": "Young dynamic team member", "language": "en", "label": True, "category": "age"},
        {"text": "Knows Kubernetes", "language": "en", "label": False, "category": "none"},
        {"text": "Dưới 30 tuổi", "language": "vi", "label": True, "category": "age"},
        {"text": "Cần một bạn trẻ năng động", "language": "vi", "label": True, "category": "age"},
    ]

    report = _evaluate(tmp_path, statements=statements)
    en, vi, overall = (report["summary"]["rules"][k] for k in ("en", "vi", "overall"))

    assert (en["tp"], en["fp"], en["fn"], en["tn"]) == (2, 1, 1, 1)
    assert en["precision"] == pytest.approx(2 / 3) and en["recall"] == pytest.approx(2 / 3)
    assert (vi["tp"], vi["fp"], vi["fn"], vi["tn"]) == (1, 0, 1, 0)
    assert vi["precision"] == 1.0 and vi["recall"] == 0.5
    assert overall["precision"] == pytest.approx(3 / 4) and overall["recall"] == pytest.approx(3 / 5)
    assert report["rule_hits"] == 4


def test_classifier_hits_lift_combined_recall_but_not_rules_recall(tmp_path):
    fake.reset()
    fake.enqueue("discrimination_check", json.dumps({"flagged": True, "category": "age", "reason": "Implies youth."}))
    statements = [{"text": "Young dynamic team member", "language": "en", "label": True, "category": "age"}]

    report = _evaluate(tmp_path, statements=statements)

    assert report["summary"]["rules"]["overall"]["recall"] == 0.0
    assert report["summary"]["combined"]["overall"]["recall"] == 1.0


def test_unchecked_results_are_counted_apart_and_not_as_positives(tmp_path, monkeypatch):
    from app.ai.types import AIProviderError

    def down(*args, **kwargs):
        raise AIProviderError("down")

    monkeypatch.setattr(discrimination.gateway, "generate_structured", down)
    statements = [{"text": "Young dynamic team member", "language": "en", "label": True, "category": "age"}]

    report = _evaluate(tmp_path, statements=statements)

    block = report["summary"]["combined"]["overall"]
    assert block["unchecked"] == 1 and block["tp"] == 0 and block["fn"] == 1


def test_every_language_has_hard_cases_on_both_sides():
    statements = run.load_statements()
    counts = Counter((s["language"], s["label"]) for s in statements)

    assert all(counts[(language, label)] >= 10 for language in LANGUAGES for label in (True, False))


def test_holdout_set_meets_the_counts_and_shares_nothing_with_the_tuning_set():
    holdout = run.load_statements(run.SETS["holdout"])
    tuning = {s["text"] for s in run.load_statements(run.SETS["statements"])}

    assert len(holdout) >= 45
    for language in LANGUAGES:
        mine = [s for s in holdout if s["language"] == language]
        assert len(mine) >= 15, language
        positives = sum(1 for s in mine if s["label"])
        assert positives == len(mine) - positives, language
    assert {s["category"] for s in holdout if s["label"]} == set(discrimination.CATEGORIES)
    assert all(s["category"] == "none" for s in holdout if not s["label"])
    assert not tuning & {s["text"] for s in holdout}
    assert len({s["text"] for s in holdout}) == len(holdout)


def test_the_report_names_the_set_used(tmp_path):
    default = _evaluate(tmp_path)
    holdout = _evaluate(tmp_path, set_name="holdout")

    assert default["set"] == "statements" and holdout["set"] == "holdout"
    assert holdout["statements"] == len(run.load_statements(run.SETS["holdout"]))
    assert "set: holdout" in run.render_markdown(holdout)
    assert "holdout" in holdout["report_files"][0]


def test_an_unknown_set_is_refused(tmp_path):
    with pytest.raises(run.EvalError):
        _evaluate(tmp_path, set_name="nope")


def test_main_passes_the_set_option_and_defaults_to_the_existing_set(monkeypatch):
    seen = {}
    monkeypatch.setattr(run, "_prepare_environment", lambda *a: None)
    monkeypatch.setattr(run, "evaluate", lambda *a, **k: seen.update(k))
    monkeypatch.setattr("app.database.migrate.run_migrations", lambda: None)

    run.main(["--profile", "fake", "--dry-run", "--set", "holdout"])
    assert seen["set_name"] == "holdout"
    run.main(["--profile", "fake", "--dry-run"])
    assert seen["set_name"] == "statements"
