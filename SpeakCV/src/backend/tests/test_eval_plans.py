import json

from eval.plans import run


def _report(tmp_path, **kwargs):
    return run.evaluate(profile="fake", confirm=lambda *_: True, reports_dir=tmp_path, **kwargs)


def test_two_sample_companies_get_plans_that_overlap_under_half(tmp_path):
    report = _report(tmp_path)

    assert len(report["plans"]) == 2
    assert all(len(plan["questions"]) >= 8 for plan in report["plans"])
    assert report["overlap"] < 0.5
    assert report["target_met"] is True


def test_overlap_is_the_jaccard_of_normalised_question_text(tmp_path):
    report = _report(tmp_path)
    left, right = ([run.normalise(q["text"]) for q in plan["questions"]] for plan in report["plans"])

    expected = len(set(left) & set(right)) / len(set(left) | set(right))
    assert report["overlap"] == expected
    assert run.jaccard(["Hello, World!"], ["hello world"]) == 1.0
    assert run.jaccard(["a b"], ["c d"]) == 0.0


def test_fake_run_says_it_shows_templates_and_the_real_measure_needs_keys(tmp_path):
    report = _report(tmp_path)

    assert report["fixture_run"] is True
    text = run.render_text(report)
    assert "does not measure real questions" in text
    assert "needs real AI keys" in text
    assert "does not measure real questions" in run.render_markdown(report)


def test_reports_are_written_and_the_plans_print_side_by_side(tmp_path):
    report = _report(tmp_path)

    names = sorted(p.suffix for p in tmp_path.iterdir())
    assert names == [".json", ".md"]
    data = json.loads(next(p for p in tmp_path.iterdir() if p.suffix == ".json").read_text(encoding="utf-8"))
    assert data["overlap"] == report["overlap"]
    table = run.side_by_side(report["plans"])
    assert all(slug in table.splitlines()[0] for slug in report["companies"])
    assert " | " in table.splitlines()[2]


def test_dry_run_and_a_declined_run_make_no_ai_call(tmp_path, capsys):
    assert run.evaluate(profile="fake", dry_run=True, reports_dir=tmp_path) is None
    assert run.evaluate(profile="fake", confirm=lambda *_: False, reports_dir=tmp_path) is None
    assert "Estimated cost" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []


def test_estimate_is_printed_before_any_ai_call(tmp_path, capsys):
    calls = []

    def confirm(text, est):
        calls.append(text)
        return True

    run.evaluate(profile="fake", confirm=confirm, reports_dir=tmp_path)
    assert calls and "Estimated cost" in calls[0]


def test_a_paid_run_needs_yes_or_a_typed_confirmation(monkeypatch):
    paid = {"complete": True, "total_usd": 0.5}
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    assert run.make_confirm(False)("", paid) is False
    assert run.make_confirm(True)("", paid) is True
    assert run.make_confirm(False)("", {"complete": True, "total_usd": 0.0}) is True
    monkeypatch.setattr("sys.stdin.isatty", lambda: True, raising=False)
    monkeypatch.setattr("builtins.input", lambda _: "yes")
    assert run.make_confirm(False)("", paid) is True
    monkeypatch.setattr("builtins.input", lambda _: "no")
    assert run.make_confirm(False)("", paid) is False
