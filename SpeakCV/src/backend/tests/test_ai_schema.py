from enum import Enum
from typing import Literal, Optional

import pytest
from pydantic import BaseModel, Field

from app.ai.schema import to_strict_schema


class Color(str, Enum):
    RED = "red"
    BLUE = "blue"


class Inner(BaseModel):
    label: str = Field(min_length=1, max_length=5)


class Outer(BaseModel):
    title: str
    score: float = 0.0
    count: int
    ok: bool
    color: Color
    kind: Literal["a", "b"]
    items: list[Inner]


def test_strict_schema_inlines_refs_and_forbids_extra_properties():
    schema = to_strict_schema(Outer)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["properties"]["color"] == {"type": "string", "enum": ["red", "blue"]}
    assert schema["properties"]["kind"] == {"type": "string", "enum": ["a", "b"]}
    inner = schema["properties"]["items"]["items"]
    assert inner == {
        "type": "object",
        "properties": {"label": {"type": "string"}},
        "required": ["label"],
        "additionalProperties": False,
    }


def test_strict_schema_rejects_optional_with_a_clear_message():
    class Bad(BaseModel):
        name: Optional[str] = None

    with pytest.raises(ValueError, match="name"):
        to_strict_schema(Bad)
