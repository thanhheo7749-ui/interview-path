import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
VENDOR_MODULES = {"anthropic", "openai", "voyageai", "edge_tts", "groq"}
VENDOR_PREFIXES = ("google.genai", "google.generativeai")
VENDOR_HOSTS = ("api.groq.com", "api.openai.com", "generativelanguage.googleapis.com", "api.anthropic.com", "newapi.")


def _source_files():
    for root in ("app", "core"):
        for path in (BACKEND / root).rglob("*.py"):
            if "ai/providers" not in path.as_posix():
                yield path


def _imports(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.module


def test_only_providers_import_vendor_sdks():
    offenders = []
    for path in _source_files():
        for name in _imports(ast.parse(path.read_text(encoding="utf-8"))):
            if name.split(".")[0] in VENDOR_MODULES or name.startswith(VENDOR_PREFIXES):
                offenders.append(f"{path.relative_to(BACKEND)}: {name}")
    assert offenders == []


def test_business_code_never_calls_vendor_hosts_directly():
    offenders = []
    for path in _source_files():
        if path.as_posix().endswith("app/ai/config.py"):
            continue  # holds the official default endpoint
        text = path.read_text(encoding="utf-8")
        offenders += [f"{path.relative_to(BACKEND)}: {host}" for host in VENDOR_HOSTS if host in text]
    assert offenders == []
