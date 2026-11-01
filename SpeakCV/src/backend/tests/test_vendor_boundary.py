import ast
from pathlib import Path

import pytest

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
            yield from (f"{node.module}.{alias.name}" for alias in node.names)


def _offending(name):
    return name.split(".")[0] in VENDOR_MODULES or name.startswith(VENDOR_PREFIXES)


@pytest.mark.parametrize("source", [
    "from google import genai",
    "from google.genai import types",
    "import google.generativeai",
    "from google import generativeai as g",
    "import anthropic",
    "from openai import OpenAI",
])
def test_every_import_form_is_seen(source):
    assert any(_offending(name) for name in _imports(ast.parse(source)))


def test_other_google_packages_are_allowed():
    assert not any(_offending(name) for name in _imports(ast.parse("from google import auth\nimport google.oauth2")))


def test_only_providers_import_vendor_sdks():
    offenders = []
    for path in _source_files():
        for name in _imports(ast.parse(path.read_text(encoding="utf-8"))):
            if _offending(name):
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
