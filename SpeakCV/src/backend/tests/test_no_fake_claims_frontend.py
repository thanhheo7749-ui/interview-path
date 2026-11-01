import re
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
FORBIDDEN = re.compile(
    r"ENTERPRISE_DEMO_PRESETS|DEMO_SAMPLE_ANSWERS|Instant HR|PII Masked|pii_anonymized|evidence_grounded"
    r"|minutes_saved|mins saved|parse-master-cv|parseMasterCv|presetPassword|presetEmail"
)


def test_removed_identifiers_are_gone_from_the_candidate_app():
    if not FRONTEND.exists():
        pytest.skip("frontend not present")
    offenders = []
    for root in ("app", "components", "services", "hooks", "context"):
        for path in (FRONTEND / root).rglob("*"):
            if path.suffix in {".ts", ".tsx"}:
                for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    if FORBIDDEN.search(line):
                        offenders.append(f"{path.relative_to(FRONTEND)}:{number}")
    assert offenders == []
