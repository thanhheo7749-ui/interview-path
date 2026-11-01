import re
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
FORBIDDEN = re.compile(
    r"ENTERPRISE_DEMO_PRESETS|DEMO_SAMPLE_ANSWERS|Instant HR|PII Masked|pii_anonymized|evidence_grounded"
    r"|minutes_saved|mins saved|parse-master-cv|parseMasterCv|presetPassword|presetEmail"
    # Candidates see gaps in Fit Compass, never the screening verdict or its field name.
    r"|does not meet|not_met|cv_status"
    # The demo admin credentials, split so this file does not carry them either.
    r"|admin" r"@gmail\.com|admin" r"123"
)


def test_removed_identifiers_are_gone_from_the_candidate_app():
    if not FRONTEND.exists():
        pytest.skip("frontend not present")
    offenders = []
    for root in ("app", "components", "services", "hooks", "context", "lib"):
        for path in (FRONTEND / root).rglob("*"):
            if path.suffix in {".ts", ".tsx"}:
                for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    if FORBIDDEN.search(line):
                        offenders.append(f"{path.relative_to(FRONTEND)}:{number}")
    assert offenders == []


def test_site_metadata_makes_no_unsupported_claims():
    if not FRONTEND.exists():
        pytest.skip("frontend not present")
    source = (FRONTEND / "app" / "layout.tsx").read_text(encoding="utf-8")
    metadata = source[source.index("export const metadata"):source.index("icons:")]
    assert 'title: "SpeakCV: every CV gets a conversation"' in metadata
    assert not re.search(r"leading|practice|instant|detailed scoring", metadata, re.I)


def test_register_form_asks_for_the_length_the_server_requires():
    if not FRONTEND.exists():
        pytest.skip("frontend not present")
    source = (FRONTEND / "app" / "register" / "page.tsx").read_text(encoding="utf-8")
    assert "minLength={10}" in source
    assert "minLength={6}" not in source
