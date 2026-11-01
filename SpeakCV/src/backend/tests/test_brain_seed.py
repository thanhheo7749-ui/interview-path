from pathlib import Path

import pytest
import yaml

from app.brain import audience as aud
from app.brain import retriever, seed
from app.brain.text import quote_in
from app.database.sql_models import Company, KbConflict, KbEdge, KbNode

ROOT = Path(__file__).resolve().parents[1] / "seed" / "sample_companies"
SLUGS = ("daehan-precision", "sori-labs")


def _truth(slug):
    return yaml.safe_load((ROOT / slug / "ground_truth.yaml").read_text(encoding="utf-8"))


def _all_text(slug):
    return "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / slug).glob("*.md"))


def _language(file_name):
    return file_name.split(".")[-2]


def test_every_ground_truth_quote_is_verbatim_in_a_document():
    for slug in SLUGS:
        text = _all_text(slug)
        truth = _truth(slug)
        for item in truth["extraction"] + truth["edges"]:
            assert quote_in(item["quote"], text), item["quote"]
        for pair in truth["contradictions"]:
            for side in ("a", "b"):
                document = (ROOT / slug / pair[side]["file"]).read_text(encoding="utf-8")
                assert quote_in(pair[side]["quote"], document), pair[side]["quote"]


def test_planted_items_meet_the_minimums():
    for slug in SLUGS:
        truth = _truth(slug)
        assert len(truth["contradictions"]) >= 3
        assert len(truth["gaps"]) >= 5
        assert len(truth["extraction"]) >= 30
        assert truth["canaries"]
        cross = [
            pair for pair in truth["contradictions"]
            if {_language(pair["a"]["file"]), _language(pair["b"]["file"])} == {"ko", "vi"}
        ]
        assert len(cross) >= 2
        # the canary is in the confidential notes and nowhere else
        holders = [p.name for p in (ROOT / slug).glob("*.md") if truth["canaries"][0] in p.read_text(encoding="utf-8")]
        assert holders == ["manager-notes.ko.md"]


def test_sample_content_is_labelled_and_fictional():
    for slug in SLUGS:
        spec = yaml.safe_load((ROOT / slug / "company.yaml").read_text(encoding="utf-8"))
        assert spec["name"].endswith("(Sample)")
        assert all(user["email"].endswith(".sample") for user in spec["users"])


def test_seed_runs_the_real_pipeline_with_fake_ai(db, tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    results = seed.seed_samples(auto_approve=True)
    db.expire_all()
    assert all(result["dropped_items"] == 0 for result in results)
    for slug in SLUGS:
        company = db.query(Company).filter_by(slug=slug).one()
        assert company.is_sample is True
        assert company.name.endswith("(Sample)")
        assert db.query(KbNode).filter_by(company_id=company.id, status="published").count() >= 30
        assert db.query(KbEdge).filter_by(company_id=company.id, status="published").count() > 0
        assert db.query(KbConflict).filter_by(company_id=company.id, status="open").count() >= 3
        assert db.query(KbNode).filter_by(company_id=company.id, status="draft").count() == 0


def test_seed_is_idempotent(db, tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    seed.seed_samples(auto_approve=True)
    counts = (db.query(KbNode).count(), db.query(KbEdge).count(), db.query(KbConflict).count())
    seed.seed_samples(auto_approve=True)
    db.expire_all()
    assert (db.query(KbNode).count(), db.query(KbEdge).count(), db.query(KbConflict).count()) == counts


def test_same_role_has_different_profiles_at_the_two_companies(db, tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    seed.seed_samples(auto_approve=True)
    db.expire_all()
    profiles = {}
    for slug in SLUGS:
        company = db.query(Company).filter_by(slug=slug).one()
        role = db.query(KbNode).filter_by(company_id=company.id, type="role", title="Backend Developer").one()
        profiles[slug] = retriever.role_profile(db, aud.candidate(company.id), role.id)
    assert {v.title for v in profiles["daehan-precision"].values} != {v.title for v in profiles["sori-labs"].values}
    assert all(profile.values for profile in profiles.values())


def test_confidential_notes_never_reach_the_candidate_profile(db, tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    seed.seed_samples(auto_approve=True)
    db.expire_all()
    for slug in SLUGS:
        company = db.query(Company).filter_by(slug=slug).one()
        role = db.query(KbNode).filter_by(company_id=company.id, type="role", title="Backend Developer").one()
        profile = retriever.role_profile(db, aud.candidate(company.id), role.id)
        assert _truth(slug)["canaries"][0] not in repr(profile)


def test_seed_only_and_unknown_slug(db, tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    seed.seed_samples(only="sori-labs")
    assert db.query(Company).filter_by(slug="daehan-precision").first() is None
    with pytest.raises(seed.SeedError):
        seed.seed_samples(only="nope")


def test_seed_refuses_a_company_that_is_not_a_sample(db, tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    db.add(Company(slug="sori-labs", name="Real", is_sample=False))
    db.commit()
    with pytest.raises(seed.SeedError):
        seed.seed_samples(only="sori-labs")


def test_generated_password_is_printed_once(db, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.delenv("SAMPLE_USER_PASSWORD", raising=False)
    seed.seed_samples(only="sori-labs")
    assert capsys.readouterr().out.count("Generated sample user password") == 1
    seed.seed_samples(only="sori-labs")
    assert "Generated sample user password" not in capsys.readouterr().out


def test_auto_approve_refuses_a_real_company(db, tmp_path, monkeypatch):
    from app.brain import ingestion
    from app.brain.review import auto_approve_document

    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    company = Company(slug="real", name="Real", is_sample=False)
    db.add(company)
    db.commit()
    document = ingestion.create_document(
        db, company.id, None, title="Doc", data=b"text", suffix=".txt",
        visibility="internal", department_id=None, language="en", effective_date=None,
    )
    with pytest.raises(PermissionError):
        auto_approve_document(db, document.id, None)
