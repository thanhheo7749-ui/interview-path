from dataclasses import dataclass

from pydantic import BaseModel


class AIError(Exception):
    """Base class for AI gateway errors."""


class AIConfigError(AIError):
    """Configuration is missing or invalid. Raised at startup."""


class AIProviderError(AIError):
    """A vendor call failed in a way that may succeed later. HTTP 503."""


class AIOutputError(AIError):
    """The vendor returned unusable output, or refused. HTTP 502. `usage` is what the call still cost, when known."""

    def __init__(self, message: str = "", usage: "Usage | None" = None):
        super().__init__(message)
        self.usage = usage


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    audio_seconds: float = 0.0
    characters: int = 0


@dataclass(frozen=True)
class ProviderText:
    text: str
    usage: Usage


@dataclass(frozen=True)
class ProviderEmbedding:
    vectors: list[list[float]]
    usage: Usage


@dataclass(frozen=True)
class ProviderTranscript:
    text: str
    language: str
    usage: Usage


@dataclass(frozen=True)
class ProviderAudio:
    audio: bytes
    mime_type: str
    usage: Usage


@dataclass(frozen=True)
class TextResult:
    text: str
    provider: str
    model: str
    usage: Usage
    latency_ms: int


@dataclass(frozen=True)
class StructuredResult:
    value: BaseModel
    raw_text: str
    provider: str
    model: str
    usage: Usage
    latency_ms: int


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: list[list[float]]
    model: str
    dimension: int
    provider: str
    usage: Usage
    latency_ms: int


@dataclass(frozen=True)
class TranscriptResult:
    text: str
    language: str
    provider: str
    model: str
    usage: Usage
    latency_ms: int


@dataclass(frozen=True)
class AudioResult:
    audio: bytes
    mime_type: str
    provider: str
    model: str
    usage: Usage
    latency_ms: int
