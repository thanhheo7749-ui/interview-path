# Interview OpenAI-Primary Fallback-Gemini Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make only the interview chat flow prefer OpenAI first and fall back to Gemini, while returning accurate provider metadata about which backend actually answered.

**Architecture:** Keep the provider-ordering logic centralized in `src/backend/app/ai_service.py`, but make it overridable per call with a `provider_priority` parameter. Update the interview route to pass `['openai', 'gemini']`, leave all other callers on the existing default order, and add focused tests for ordering, fallback, and metadata.

**Tech Stack:** Python 3.12, FastAPI, pytest, requests, google-generativeai

---

## File structure

- **Modify:** `src/backend/app/ai_service.py`
  - Add provider-priority override support for chat calls.
  - Return the actual winning provider in metadata instead of inferring from env vars.
- **Modify:** `src/backend/app/routers/interview.py`
  - Pass interview-specific priority `['openai', 'gemini']` into the shared AI service.
- **Create:** `src/backend/tests/test_ai_service.py`
  - Add focused tests for default ordering, interview override ordering, fallback, and metadata.

### Task 1: Add a failing test for default provider order staying unchanged

**Files:**
- Create: `src/backend/tests/test_ai_service.py`
- Modify: `src/backend/app/ai_service.py`
- Test: `src/backend/tests/test_ai_service.py`

- [ ] **Step 1: Write the failing test**

```python
from app import ai_service


def test_call_ai_chat_prefers_gemini_by_default(monkeypatch):
    calls = []

    monkeypatch.setattr(ai_service, "GEMINI_API_KEY", "gemini-key")
    monkeypatch.setattr(ai_service, "OPENAI_API_KEY", "openai-key")

    def fake_gemini(messages, model, temperature, max_tokens, response_format=None, timeout=90):
        calls.append("gemini")
        return "gemini ok"

    def fake_openai(messages, model, temperature, max_tokens, response_format=None, timeout=90):
        calls.append("openai")
        return "openai ok"

    monkeypatch.setattr(ai_service, "_call_gemini", fake_gemini)
    monkeypatch.setattr(ai_service, "_call_openai", fake_openai)

    result = ai_service.call_ai_chat(messages=[{"role": "user", "content": "hello"}])

    assert result == "gemini ok"
    assert calls == ["gemini"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest "c:\TepD\Tep_Code\AI-web(SpeakCV)\SpeakCV\src\backend\tests\test_ai_service.py::test_call_ai_chat_prefers_gemini_by_default" -v
```

Expected: FAIL because `test_ai_service.py` does not exist yet or because the test file exists but the imported behavior has not been fully implemented.

- [ ] **Step 3: Write minimal implementation support for the test file only**

Create `src/backend/tests/test_ai_service.py` with:

```python
from app import ai_service


def test_call_ai_chat_prefers_gemini_by_default(monkeypatch):
    calls = []

    monkeypatch.setattr(ai_service, "GEMINI_API_KEY", "gemini-key")
    monkeypatch.setattr(ai_service, "OPENAI_API_KEY", "openai-key")

    def fake_gemini(messages, model, temperature, max_tokens, response_format=None, timeout=90):
        calls.append("gemini")
        return "gemini ok"

    def fake_openai(messages, model, temperature, max_tokens, response_format=None, timeout=90):
        calls.append("openai")
        return "openai ok"

    monkeypatch.setattr(ai_service, "_call_gemini", fake_gemini)
    monkeypatch.setattr(ai_service, "_call_openai", fake_openai)

    result = ai_service.call_ai_chat(messages=[{"role": "user", "content": "hello"}])

    assert result == "gemini ok"
    assert calls == ["gemini"]
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
python -m pytest "c:\TepD\Tep_Code\AI-web(SpeakCV)\SpeakCV\src\backend\tests\test_ai_service.py::test_call_ai_chat_prefers_gemini_by_default" -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/backend/tests/test_ai_service.py
git commit -m "test: cover default ai provider order"
```

### Task 2: Add a failing test for interview-specific OpenAI-first override

**Files:**
- Modify: `src/backend/tests/test_ai_service.py`
- Modify: `src/backend/app/ai_service.py`
- Test: `src/backend/tests/test_ai_service.py`

- [ ] **Step 1: Write the failing test**

Append this test to `src/backend/tests/test_ai_service.py`:

```python
def test_call_ai_chat_uses_openai_first_when_priority_requests_it(monkeypatch):
    calls = []

    monkeypatch.setattr(ai_service, "GEMINI_API_KEY", "gemini-key")
    monkeypatch.setattr(ai_service, "OPENAI_API_KEY", "openai-key")

    def fake_gemini(messages, model, temperature, max_tokens, response_format=None, timeout=90):
        calls.append("gemini")
        return "gemini ok"

    def fake_openai(messages, model, temperature, max_tokens, response_format=None, timeout=90):
        calls.append("openai")
        return "openai ok"

    monkeypatch.setattr(ai_service, "_call_gemini", fake_gemini)
    monkeypatch.setattr(ai_service, "_call_openai", fake_openai)

    result = ai_service.call_ai_chat(
        messages=[{"role": "user", "content": "hello"}],
        provider_priority=["openai", "gemini"],
    )

    assert result == "openai ok"
    assert calls == ["openai"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest "c:\TepD\Tep_Code\AI-web(SpeakCV)\SpeakCV\src\backend\tests\test_ai_service.py::test_call_ai_chat_uses_openai_first_when_priority_requests_it" -v
```

Expected: FAIL with `TypeError` because `call_ai_chat()` does not yet accept `provider_priority`.

- [ ] **Step 3: Write minimal implementation**

Update the signatures and provider loop in `src/backend/app/ai_service.py` to support per-call ordering:

```python
def call_ai_chat(
    messages: list,
    model: str = "gpt-4o-mini",
    temperature: float = 0.7,
    max_tokens: int = None,
    response_format: dict = None,
    timeout: int = 90,
    provider_priority: list[str] | None = None,
) -> str:
    priority = provider_priority or ["gemini", "openai"]

    for provider in priority:
        if provider == "gemini" and GEMINI_API_KEY:
            try:
                gemini_model = GEMINI_MODEL_MAP.get(model, "gemini-2.0-flash")
                print(f"🔄 Trying Gemini ({gemini_model})...")
                return _call_gemini(messages, model, temperature, max_tokens, response_format, timeout)
            except Exception as e:
                print(f"⚠️ Gemini failed: {e}")
        elif provider == "openai" and OPENAI_API_KEY:
            try:
                routed_model = {
                    "gpt-4o-mini": OPENAI_MODEL_GPT4O_MINI,
                    "gpt-4o": OPENAI_MODEL_GPT4O,
                }.get(model, model)
                print(f"🔄 Trying OpenAI ({routed_model})...")
                return _call_openai(messages, model, temperature, max_tokens, response_format, timeout)
            except Exception as e:
                print(f"⚠️ OpenAI failed: {e}")

    raise Exception("No AI provider succeeded.")
```

Do not finalize the error text here; later tasks will tighten metadata and error reporting.

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
python -m pytest "c:\TepD\Tep_Code\AI-web(SpeakCV)\SpeakCV\src\backend\tests\test_ai_service.py::test_call_ai_chat_uses_openai_first_when_priority_requests_it" -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/backend/tests/test_ai_service.py src/backend/app/ai_service.py
git commit -m "feat: support per-call ai provider priority"
```

### Task 3: Add a failing test for accurate provider metadata

**Files:**
- Modify: `src/backend/tests/test_ai_service.py`
- Modify: `src/backend/app/ai_service.py`
- Test: `src/backend/tests/test_ai_service.py`

- [ ] **Step 1: Write the failing test**

Append this test to `src/backend/tests/test_ai_service.py`:

```python
def test_call_ai_chat_with_meta_reports_actual_provider(monkeypatch):
    monkeypatch.setattr(ai_service, "GEMINI_API_KEY", "gemini-key")
    monkeypatch.setattr(ai_service, "OPENAI_API_KEY", "openai-key")

    def fake_openai(messages, model, temperature, max_tokens, response_format=None, timeout=90):
        return "openai ok"

    def fake_gemini(messages, model, temperature, max_tokens, response_format=None, timeout=90):
        return "gemini ok"

    monkeypatch.setattr(ai_service, "_call_openai", fake_openai)
    monkeypatch.setattr(ai_service, "_call_gemini", fake_gemini)

    result = ai_service.call_ai_chat_with_meta(
        messages=[{"role": "user", "content": "hello"}],
        provider_priority=["openai", "gemini"],
    )

    assert result["content"] == "openai ok"
    assert result["provider"] == "openai"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest "c:\TepD\Tep_Code\AI-web(SpeakCV)\SpeakCV\src\backend\tests\test_ai_service.py::test_call_ai_chat_with_meta_reports_actual_provider" -v
```

Expected: FAIL because `call_ai_chat_with_meta()` still infers the provider from env vars and will return `gemini` when both keys exist.

- [ ] **Step 3: Write minimal implementation**

Refactor `src/backend/app/ai_service.py` so the service returns both content and winning provider internally:

```python
def _call_ai_with_provider(
    messages: list,
    model: str,
    temperature: float,
    max_tokens: int = None,
    response_format: dict = None,
    timeout: int = 90,
    provider_priority: list[str] | None = None,
) -> tuple[str, str]:
    priority = provider_priority or ["gemini", "openai"]
    errors = []

    for provider in priority:
        if provider == "gemini":
            if not GEMINI_API_KEY:
                continue
            try:
                gemini_model = GEMINI_MODEL_MAP.get(model, "gemini-2.0-flash")
                print(f"🔄 Trying Gemini ({gemini_model})...")
                return _call_gemini(messages, model, temperature, max_tokens, response_format, timeout), "gemini"
            except Exception as e:
                print(f"⚠️ Gemini failed: {e}")
                errors.append(f"gemini: {e}")
        elif provider == "openai":
            if not OPENAI_API_KEY:
                continue
            try:
                routed_model = {
                    "gpt-4o-mini": OPENAI_MODEL_GPT4O_MINI,
                    "gpt-4o": OPENAI_MODEL_GPT4O,
                }.get(model, model)
                print(f"🔄 Trying OpenAI ({routed_model})...")
                return _call_openai(messages, model, temperature, max_tokens, response_format, timeout), "openai"
            except Exception as e:
                print(f"⚠️ OpenAI failed: {e}")
                errors.append(f"openai: {e}")

    if errors:
        raise Exception("Both configured AI providers failed: " + " | ".join(errors))
    raise Exception("No AI API keys configured (GEMINI_API_KEY and OPENAI_API_KEY are both missing).")


def call_ai_chat(..., provider_priority: list[str] | None = None) -> str:
    content, _provider = _call_ai_with_provider(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format,
        timeout=timeout,
        provider_priority=provider_priority,
    )
    return content


def call_ai_chat_with_meta(..., provider_priority: list[str] | None = None) -> dict:
    started_at = time.time()
    content, provider = _call_ai_with_provider(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format,
        timeout=timeout,
        provider_priority=provider_priority,
    )
    return {
        "content": content,
        "provider": provider,
        "model": model,
        "latency_ms": int((time.time() - started_at) * 1000),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
python -m pytest "c:\TepD\Tep_Code\AI-web(SpeakCV)\SpeakCV\src\backend\tests\test_ai_service.py::test_call_ai_chat_with_meta_reports_actual_provider" -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/backend/tests/test_ai_service.py src/backend/app/ai_service.py
git commit -m "fix: report actual ai provider in metadata"
```

### Task 4: Add a failing test for fallback from OpenAI to Gemini

**Files:**
- Modify: `src/backend/tests/test_ai_service.py`
- Modify: `src/backend/app/ai_service.py`
- Test: `src/backend/tests/test_ai_service.py`

- [ ] **Step 1: Write the failing test**

Append this test to `src/backend/tests/test_ai_service.py`:

```python
def test_call_ai_chat_with_meta_falls_back_to_gemini_after_openai_failure(monkeypatch):
    calls = []

    monkeypatch.setattr(ai_service, "GEMINI_API_KEY", "gemini-key")
    monkeypatch.setattr(ai_service, "OPENAI_API_KEY", "openai-key")

    def fake_openai(messages, model, temperature, max_tokens, response_format=None, timeout=90):
        calls.append("openai")
        raise Exception("openai quota")

    def fake_gemini(messages, model, temperature, max_tokens, response_format=None, timeout=90):
        calls.append("gemini")
        return "gemini recovered"

    monkeypatch.setattr(ai_service, "_call_openai", fake_openai)
    monkeypatch.setattr(ai_service, "_call_gemini", fake_gemini)

    result = ai_service.call_ai_chat_with_meta(
        messages=[{"role": "user", "content": "hello"}],
        provider_priority=["openai", "gemini"],
    )

    assert calls == ["openai", "gemini"]
    assert result["content"] == "gemini recovered"
    assert result["provider"] == "gemini"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest "c:\TepD\Tep_Code\AI-web(SpeakCV)\SpeakCV\src\backend\tests\test_ai_service.py::test_call_ai_chat_with_meta_falls_back_to_gemini_after_openai_failure" -v
```

Expected: FAIL until the shared helper fully preserves ordered fallback while returning the winning provider.

- [ ] **Step 3: Write minimal implementation**

Tighten `_call_ai_with_provider()` in `src/backend/app/ai_service.py` so it:
- preserves provider order exactly
- continues after first-provider failure
- returns the winning provider from the fallback path
- keeps a combined error list only if every attempted provider fails

No new public API is needed beyond `provider_priority`.

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
python -m pytest "c:\TepD\Tep_Code\AI-web(SpeakCV)\SpeakCV\src\backend\tests\test_ai_service.py::test_call_ai_chat_with_meta_falls_back_to_gemini_after_openai_failure" -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/backend/tests/test_ai_service.py src/backend/app/ai_service.py
git commit -m "test: cover ordered ai fallback"
```

### Task 5: Add a failing test that the interview route requests OpenAI-first priority

**Files:**
- Modify: `src/backend/tests/test_ai_service.py`
- Modify: `src/backend/app/routers/interview.py`
- Test: `src/backend/tests/test_ai_service.py`

- [ ] **Step 1: Write the failing test**

Append this test to `src/backend/tests/test_ai_service.py`:

```python
from app.routers import interview


def test_interview_route_requests_openai_then_gemini():
    source = interview.chat.__code__.co_consts
    assert any("openai" in str(item) and "gemini" in str(item) for item in source)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest "c:\TepD\Tep_Code\AI-web(SpeakCV)\SpeakCV\src\backend\tests\test_ai_service.py::test_interview_route_requests_openai_then_gemini" -v
```

Expected: FAIL because the interview route does not yet pass an explicit provider priority.

- [ ] **Step 3: Write minimal implementation**

Update the AI call in `src/backend/app/routers/interview.py:475-481` to:

```python
            llm_result = call_ai_chat_with_meta(
                messages=messages,
                model="gpt-4o-mini",
                temperature=temperature,
                max_tokens=250,
                timeout=90,
                provider_priority=["openai", "gemini"],
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
python -m pytest "c:\TepD\Tep_Code\AI-web(SpeakCV)\SpeakCV\src\backend\tests\test_ai_service.py::test_interview_route_requests_openai_then_gemini" -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/backend/tests/test_ai_service.py src/backend/app/routers/interview.py
git commit -m "feat: prefer openai for interview chat"
```

### Task 6: Run the focused regression suite

**Files:**
- Modify: `src/backend/tests/test_ai_service.py`
- Modify: `src/backend/app/ai_service.py`
- Modify: `src/backend/app/routers/interview.py`
- Test: `src/backend/tests/test_ai_service.py`
- Test: `src/backend/tests/test_orchestrator.py`
- Test: `src/backend/tests/test_interview_context.py`

- [ ] **Step 1: Run the focused backend tests**

Run:

```powershell
python -m pytest "c:\TepD\Tep_Code\AI-web(SpeakCV)\SpeakCV\src\backend\tests\test_ai_service.py" "c:\TepD\Tep_Code\AI-web(SpeakCV)\SpeakCV\src\backend\tests\test_orchestrator.py" "c:\TepD\Tep_Code\AI-web(SpeakCV)\SpeakCV\src\backend\tests\test_interview_context.py" -v
```

Expected: PASS for all tests.

- [ ] **Step 2: If any provider-order tests fail, align implementation with these exact signatures**

`src/backend/app/ai_service.py` should expose:

```python
def call_ai_chat(
    messages: list,
    model: str = "gpt-4o-mini",
    temperature: float = 0.7,
    max_tokens: int = None,
    response_format: dict = None,
    timeout: int = 90,
    provider_priority: list[str] | None = None,
) -> str:
    ...


def call_ai_chat_with_meta(
    messages: list,
    model: str = "gpt-4o-mini",
    temperature: float = 0.7,
    max_tokens: int = None,
    response_format: dict = None,
    timeout: int = 90,
    provider_priority: list[str] | None = None,
) -> dict:
    ...
```

- [ ] **Step 3: Re-run the focused backend tests**

Run:

```powershell
python -m pytest "c:\TepD\Tep_Code\AI-web(SpeakCV)\SpeakCV\src\backend\tests\test_ai_service.py" "c:\TepD\Tep_Code\AI-web(SpeakCV)\SpeakCV\src\backend\tests\test_orchestrator.py" "c:\TepD\Tep_Code\AI-web(SpeakCV)\SpeakCV\src\backend\tests\test_interview_context.py" -v
```

Expected: PASS for all tests.

- [ ] **Step 4: Commit**

```bash
git add src/backend/tests/test_ai_service.py src/backend/app/ai_service.py src/backend/app/routers/interview.py
git commit -m "fix: use openai first for interview ai"
```

## Self-review

- **Spec coverage:**
  - Interview-only override is covered by Task 5.
  - Shared per-call override without changing global defaults is covered by Tasks 1 and 2.
  - Accurate provider metadata is covered by Task 3.
  - Ordered fallback from OpenAI to Gemini is covered by Task 4.
  - Focused regression testing is covered by Task 6.
- **Placeholder scan:** Removed `TODO`/`TBD`; each task includes file paths, test code, commands, and expected outcomes.
- **Type consistency:** `provider_priority: list[str] | None = None` is used consistently in every planned service signature and interview call site.
