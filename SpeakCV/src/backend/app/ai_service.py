"""
AI Service Module — Centralized AI API calls.
Primary: Google Gemini (Gemini 2.0 Flash)
Fallback: OpenAI (newapi.ccfilm.online)
"""

import os
import json
import time
import requests
import google.generativeai as genai
from dotenv import load_dotenv
from pathlib import Path

# Load root project .env first, then local .env overrides
_resolved = Path(__file__).resolve()
_root_candidate = _resolved.parents[2] / ".env"
if _root_candidate.exists():
    load_dotenv(_root_candidate)
load_dotenv(override=True)  # local src/backend/.env overrides

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL_GPT4O_MINI = os.getenv("OPENAI_MODEL_GPT4O_MINI", "gpt-4.1-mini")
OPENAI_MODEL_GPT4O = os.getenv("OPENAI_MODEL_GPT4O", "gpt-4.1")

# --- Model mapping: OpenAI model names → Gemini equivalents ---
GEMINI_MODEL_MAP = {
    "gpt-4.1-mini": "gemini-2.0-flash",
    "gpt-4.1": "gemini-2.0-flash",
    "gpt-4o-mini": "gemini-2.0-flash",
    "gpt-4o": "gemini-2.0-flash",
    "gpt-4": "gemini-2.0-flash",
}

# --- Configure Gemini SDK ---
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def _convert_messages_for_gemini(messages: list) -> tuple:
    """
    Convert OpenAI-style messages to Gemini format.
    Returns (system_instruction, chat_history) tuple.
    """
    system_instruction = ""
    chat_history = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if role == "system":
            system_instruction += content + "\n"
        elif role == "assistant":
            chat_history.append({"role": "model", "parts": [content]})
        else:  # "user"
            chat_history.append({"role": "user", "parts": [content]})

    return system_instruction.strip(), chat_history


def _call_gemini(messages, model, temperature, max_tokens, response_format=None, timeout=90):
    """Call Google Gemini API."""
    gemini_model_name = GEMINI_MODEL_MAP.get(model, "gemini-2.0-flash")
    system_instruction, chat_history = _convert_messages_for_gemini(messages)

    generation_config = {
        "temperature": temperature,
    }
    if max_tokens:
        generation_config["max_output_tokens"] = max_tokens
    if response_format and response_format.get("type") == "json_object":
        generation_config["response_mime_type"] = "application/json"

    model_instance = genai.GenerativeModel(
        model_name=gemini_model_name,
        system_instruction=system_instruction if system_instruction else None,
        generation_config=generation_config,
    )

    # Build the conversation: all messages except the last one are history
    if len(chat_history) > 1:
        history = chat_history[:-1]
        last_message = chat_history[-1]["parts"][0]
    elif len(chat_history) == 1:
        history = []
        last_message = chat_history[0]["parts"][0]
    else:
        history = []
        last_message = "Hello"

    chat = model_instance.start_chat(history=history)
    response = chat.send_message(last_message)

    return response.text


def _call_openai(messages, model, temperature, max_tokens, response_format=None, timeout=90):
    """Call the fallback OpenAI-compatible API."""
    routed_model = {
        "gpt-4.1-mini": OPENAI_MODEL_GPT4O_MINI,
        "gpt-4.1": OPENAI_MODEL_GPT4O,
        "gpt-4o-mini": OPENAI_MODEL_GPT4O_MINI,
        "gpt-4o": OPENAI_MODEL_GPT4O,
    }.get(model, model)

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": routed_model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens:
        data["max_tokens"] = max_tokens
    if response_format:
        data["response_format"] = response_format

    res = requests.post(f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions", headers=headers, json=data, timeout=timeout)

    if res.status_code == 200:
        return res.json()["choices"][0]["message"]["content"]
    else:
        raise Exception(f"OpenAI API error (status {res.status_code}): {res.text[:200]}")


def call_ai_chat(
    messages: list,
    model: str = "gpt-4.1-mini",
    temperature: float = 0.7,
    max_tokens: int = None,
    response_format: dict = None,
    timeout: int = 90,
) -> str:
    """
    Call AI using Gemini (primary) or OpenAI (fallback).
    Returns the AI response text.
    """
    # --- Try Gemini first ---
    if GEMINI_API_KEY:
        try:
            gemini_model = GEMINI_MODEL_MAP.get(model, "gemini-2.0-flash")
            print(f"🔄 Trying Gemini ({gemini_model})...")
            result = _call_gemini(messages, model, temperature, max_tokens, response_format, timeout)
            print(f"✅ Gemini responded successfully.")
            return result
        except Exception as e:
            print(f"⚠️ Gemini failed: {e}")
            # Fall through to OpenAI

    # --- Fallback to OpenAI ---
    if OPENAI_API_KEY:
        try:
            routed_model = {
                "gpt-4.1-mini": OPENAI_MODEL_GPT4O_MINI,
                "gpt-4.1": OPENAI_MODEL_GPT4O,
                "gpt-4o-mini": OPENAI_MODEL_GPT4O_MINI,
                "gpt-4o": OPENAI_MODEL_GPT4O,
            }.get(model, model)
            print(f"🔄 Falling back to OpenAI ({routed_model})...")
            result = _call_openai(messages, model, temperature, max_tokens, response_format, timeout)
            print(f"✅ OpenAI responded successfully.")
            return result
        except Exception as e:
            print(f"⚠️ OpenAI also failed: {e}")
            raise Exception("Both Gemini and OpenAI failed: " + str(e))

    raise Exception("No AI API keys configured (GEMINI_API_KEY and OPENAI_API_KEY are both missing).")


def call_ai_chat_with_meta(
    messages: list,
    model: str = "gpt-4.1-mini",
    temperature: float = 0.7,
    max_tokens: int = None,
    response_format: dict = None,
    timeout: int = 90,
) -> dict:
    started_at = time.time()
    content = call_ai_chat(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format,
        timeout=timeout,
    )
    provider = "gemini" if GEMINI_API_KEY else "openai"
    return {
        "content": content,
        "provider": provider,
        "model": model,
        "latency_ms": int((time.time() - started_at) * 1000),
    }


__all__ = ["call_ai_chat", "call_ai_chat_stream", "call_ai_chat_with_meta"]


def call_ai_chat_stream(
    messages: list,
    model: str = "gpt-4.1",
    temperature: float = 0.7,
    timeout: int = 90,
):
    """
    Generator that yields text chunks.
    Primary: Gemini streaming. Fallback: OpenAI streaming.
    """
    # --- Try Gemini streaming first ---
    if GEMINI_API_KEY:
        try:
            gemini_model_name = GEMINI_MODEL_MAP.get(model, "gemini-2.0-flash")
            print(f"🔄 Trying Gemini streaming ({gemini_model_name})...")

            system_instruction, chat_history = _convert_messages_for_gemini(messages)

            generation_config = {
                "temperature": temperature,
            }

            model_instance = genai.GenerativeModel(
                model_name=gemini_model_name,
                system_instruction=system_instruction if system_instruction else None,
                generation_config=generation_config,
            )

            if len(chat_history) > 1:
                history = chat_history[:-1]
                last_message = chat_history[-1]["parts"][0]
            elif len(chat_history) == 1:
                history = []
                last_message = chat_history[0]["parts"][0]
            else:
                history = []
                last_message = "Hello"

            chat = model_instance.start_chat(history=history)
            response = chat.send_message(last_message, stream=True)

            print(f"✅ Gemini streaming started.")
            for chunk in response:
                if chunk.text:
                    yield chunk.text
            return  # Success, don't fallback
        except Exception as e:
            print(f"⚠️ Gemini streaming failed: {e}")
            # Fall through to OpenAI

    # --- Fallback to OpenAI streaming ---
    if OPENAI_API_KEY:
        try:
            routed_model = {
                "gpt-4.1-mini": OPENAI_MODEL_GPT4O_MINI,
                "gpt-4.1": OPENAI_MODEL_GPT4O,
                "gpt-4o-mini": OPENAI_MODEL_GPT4O_MINI,
                "gpt-4o": OPENAI_MODEL_GPT4O,
            }.get(model, model)
            print(f"🔄 Falling back to OpenAI streaming ({routed_model})...")
            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            }
            data = {
                "model": routed_model,
                "messages": messages,
                "temperature": temperature,
                "stream": True,
            }

            res = requests.post(f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions", headers=headers, json=data, stream=True, timeout=timeout)

            if res.status_code == 200:
                print(f"✅ OpenAI streaming started.")
                for line in res.iter_lines():
                    if line:
                        line_text = line.decode("utf-8")
                        if line_text.startswith("data: ") and line_text != "data: [DONE]":
                            try:
                                chunk_data = json.loads(line_text[6:].strip())
                                choices = chunk_data.get("choices", [])
                                if choices and len(choices) > 0:
                                    delta = choices[0].get("delta", {}).get("content", "")
                                    if delta:
                                        yield delta
                            except json.JSONDecodeError:
                                continue
                return  # Success
            else:
                print(f"⚠️ OpenAI streaming error (status {res.status_code})")
        except Exception as e:
            print(f"⚠️ OpenAI streaming failed: {e}")
            yield f"\n\n**Error: OpenAI streaming failed.** {str(e)}"
            return

    else:
        yield "\n\n**Error: No AI API keys configured (GEMINI_API_KEY and OPENAI_API_KEY are both missing).**"
