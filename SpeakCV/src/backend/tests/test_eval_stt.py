import pytest
import yaml

from eval.stt import run


@pytest.mark.parametrize("ref,hyp,expected", [
    ("abc", "abc", 0.0), ("abc", "abd", 1 / 3), ("abc", "", 1.0), ("", "", 0.0),
    ("Xin chào", "xin  chào", 0.0), ("연차 휴가", "연차휴가", 0.0), ("Xin chào.", "Xin chào", 0.0),
    ("", "abc", 1.0),
])
def test_character_error_rate_ignores_case_spacing_and_punctuation(ref, hyp, expected):
    assert run.character_error_rate(ref, hyp) == pytest.approx(expected)


def test_evaluate_reports_per_language_and_the_gate(tmp_path):
    (tmp_path / "a.webm").write_bytes("xin chào".encode())
    (tmp_path / "b.webm").write_bytes("hello world".encode())
    (tmp_path / "c.webm").write_bytes("wrong words here".encode())
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(yaml.safe_dump({"clips": [
        {"file": "a.webm", "language": "vi", "reference": "xin chào"},
        {"file": "b.webm", "language": "en", "reference": "hello world"},
        {"file": "c.webm", "language": "ko", "reference": "연차 휴가"},
    ]}), encoding="utf-8")
    report = run.evaluate(manifest, confirm=lambda _: True)
    assert report["languages"]["vi"]["cer"] == 0.0
    assert report["languages"]["en"]["gate_passed"] is True
    assert report["languages"]["ko"]["gate_passed"] is False
    assert report["gate_passed"] is False
    assert report["provider"] == "fake"
    assert report["languages"]["vi"]["avg_latency_ms"] >= 0


def test_fake_run_says_plainly_that_it_measures_nothing(tmp_path):
    (tmp_path / "a.webm").write_bytes(b"x")
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(yaml.safe_dump({"clips": [{"file": "a.webm", "language": "vi", "reference": "x"}]}), encoding="utf-8")
    report = run.evaluate(manifest, confirm=lambda _: True, reports_dir=tmp_path / "reports")
    assert report["fixture_run"] is True
    assert "measure" in report["note"].lower()
    markdown, data = (tmp_path / "reports").glob("stt-fake-*.md"), (tmp_path / "reports").glob("stt-fake-*.json")
    assert "measures no real speech" in next(markdown).read_text(encoding="utf-8").lower()
    assert next(data).exists()


def test_missing_manifest_explains_what_to_do(tmp_path):
    with pytest.raises(SystemExit, match="manifest"):
        run.evaluate(tmp_path / "none.yaml", confirm=lambda _: True)


def test_missing_clip_file_is_named(tmp_path):
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(yaml.safe_dump({"clips": [{"file": "gone.webm", "language": "vi", "reference": "x"}]}), encoding="utf-8")
    with pytest.raises(SystemExit, match="gone.webm"):
        run.evaluate(manifest, confirm=lambda _: True)


def test_declining_makes_no_calls(tmp_path):
    (tmp_path / "a.webm").write_bytes(b"x")
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(yaml.safe_dump({"clips": [{"file": "a.webm", "language": "vi", "reference": "x"}]}), encoding="utf-8")
    assert run.evaluate(manifest, confirm=lambda _: False) is None
