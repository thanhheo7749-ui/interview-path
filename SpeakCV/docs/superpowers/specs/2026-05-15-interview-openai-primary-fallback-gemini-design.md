# Interview AI Provider Priority Design

## Goal
Make the interview chat flow prefer OpenAI first and use Gemini only as fallback, without changing provider behavior for other backend features.

## Scope
This change applies only to the interview flow that calls [src/backend/app/routers/interview.py](src/backend/app/routers/interview.py) through `call_ai_chat_with_meta`.

Out of scope:
- CV routes
- jobs routes
- support or admin AI routes
- global default provider ordering for the shared AI service

## Current behavior
The shared AI service in [src/backend/app/ai_service.py](src/backend/app/ai_service.py) currently tries Gemini first, then falls back to OpenAI. The interview route uses that shared default, so interview requests hit Gemini even when the desired behavior is to prioritize OpenAI.

The service also reports `provider` metadata by checking whether `GEMINI_API_KEY` exists, which can misreport the actual provider used when fallback happens.

## Recommended approach
Add an optional `provider_priority` parameter to `call_ai_chat` and `call_ai_chat_with_meta` in [src/backend/app/ai_service.py](src/backend/app/ai_service.py).

For interview requests only, pass `provider_priority=["openai", "gemini"]` from [src/backend/app/routers/interview.py](src/backend/app/routers/interview.py).

All other callers will continue using the existing default priority.

## Design details

### 1. Shared AI service behavior
The shared AI service should:
- keep its existing default priority for callers that do not specify one
- support an override priority list such as `["openai", "gemini"]`
- try providers in the given order
- skip providers whose API key is missing
- preserve the current fallback behavior when the first provider fails
- raise a single error only after all allowed providers fail

### 2. Interview route behavior
The interview route should explicitly request OpenAI-first behavior when calling the shared AI service.

That keeps the policy local to the interview flow instead of changing backend-wide behavior.

### 3. Provider metadata and logging
`call_ai_chat_with_meta` should return the provider that actually produced the response, not infer it from which environment variable exists.

Logs should also reflect the real order attempted, for example:
- `Trying OpenAI (...)`
- `OpenAI failed: ...`
- `Falling back to Gemini (...)`

This makes quota or credential failures easier to diagnose.

## Error handling
If OpenAI is selected first but `OPENAI_API_KEY` is missing, the service should skip OpenAI and try Gemini if Gemini is allowed by the priority list and configured.

If both providers are unavailable or both fail, the service should raise one combined error that makes the attempted providers clear.

## Testing
Add focused tests that cover:
- interview flow requesting OpenAI-first priority
- fallback to Gemini when OpenAI fails
- metadata reporting the winning provider accurately
- default behavior for non-interview callers remaining unchanged

## Why this approach
This is the smallest change that:
- solves the interview-specific provider preference problem
- avoids duplicating AI call logic
- avoids changing unrelated routes
- fixes misleading provider metadata at the same time
