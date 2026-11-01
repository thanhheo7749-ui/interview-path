import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
FORBIDDEN = re.compile(
    r"pii_anonymized|evidence_grounded|minutes_saved|MOCK_JOBS|parse-master-cv|parse_master_cv"
    r"|knowledge_graph|get_next_topic|networkx"
)


def test_removed_identifiers_are_gone_from_active_backend_code():
    offenders = []
    roots = [BACKEND / "app", BACKEND / "core", BACKEND / "requirements.txt"]
    for root in roots:
        files = [root] if root.is_file() else root.rglob("*.py")
        for path in files:
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if FORBIDDEN.search(line):
                    offenders.append(f"{path.relative_to(BACKEND)}:{number}")
    assert offenders == []
