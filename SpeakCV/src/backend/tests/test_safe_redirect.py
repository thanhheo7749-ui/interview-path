"""Runs the real lib/safeRedirect.ts under Node, which strips the types."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[2] / "frontend" / "lib" / "safeRedirect.ts"
ORIGIN = "https://speak.example"
FALLBACK = "/fallback"

CASES = [
    ("/profile", "/profile"),
    ("/interview?id=3#top", "/interview?id=3#top"),
    ("https://speak.example/profile?a=1", "/profile?a=1"),
    ("/\t/evil.example", FALLBACK),
    ("/\n/evil.example", FALLBACK),
    ("//evil.example", FALLBACK),
    ("/\\evil.example", FALLBACK),
    ("\\\\evil.example", FALLBACK),
    ("/.//evil.example", FALLBACK),
    ("/x/..//evil.example", FALLBACK),
    ("https://evil.example/", FALLBACK),
    ("javascript:alert(1)", FALLBACK),
    ("data:text/html,x", FALLBACK),
    ("", FALLBACK),
    (None, FALLBACK),
]


def _run(inputs):
    if shutil.which("node") is None:
        pytest.skip("node is not available")
    script = (
        f"import({json.dumps(MODULE.as_uri())}).then(({{ safeRedirect }}) => "
        f"console.log(JSON.stringify({json.dumps(inputs)}.map((v) => safeRedirect(v, {json.dumps(FALLBACK)}, {json.dumps(ORIGIN)})))))"
    )
    result = subprocess.run(["node", "--experimental-strip-types", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_only_same_origin_paths_are_returned():
    assert _run([value for value, _ in CASES]) == [expected for _, expected in CASES]


@pytest.mark.parametrize("relative", ["app/login/page.tsx", "context/AuthContext.tsx"])
def test_both_call_sites_use_the_helper(relative):
    source = (MODULE.parents[1] / relative).read_text(encoding="utf-8")
    assert "safeRedirect(" in source
    assert "(?![/\\\\])" not in source
