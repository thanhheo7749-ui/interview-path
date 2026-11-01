from pydantic import BaseModel

PRIMITIVES = {"string", "number", "integer", "boolean"}
MAX_DEPTH = 16


def to_strict_schema(model: type[BaseModel]) -> dict:
    """Convert a Pydantic model to the JSON schema subset every vendor accepts.

    Objects, arrays, strings, numbers, booleans and enums only. Every property is required and
    additional properties are forbidden. Other constraints stay in Pydantic and run after the response.
    """
    raw = model.model_json_schema()
    return _convert(raw, raw.get("$defs", {}), model.__name__, 0)


def _unsupported(path: str, node: dict) -> ValueError:
    return ValueError(
        f"Unsupported schema at {path}: {sorted(node)}. Use objects, arrays, strings, numbers, "
        "booleans and enums only. Optional and unions are not allowed; use an empty value instead."
    )


def _convert(node: dict, defs: dict, path: str, depth: int) -> dict:
    if depth > MAX_DEPTH:
        raise ValueError(f"Schema at {path} is too deep or recursive.")
    if "$ref" in node:
        return _convert(defs[node["$ref"].rsplit("/", 1)[1]], defs, path, depth + 1)
    if "enum" in node:
        return {"type": node.get("type", "string"), "enum": list(node["enum"])}
    if "const" in node:
        return {"type": node.get("type", "string"), "enum": [node["const"]]}
    node_type = node.get("type")
    if node_type == "object" and "properties" in node:
        properties = {
            name: _convert(child, defs, f"{path}.{name}", depth + 1)
            for name, child in node["properties"].items()
        }
        return {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        }
    if node_type == "array" and "items" in node:
        return {"type": "array", "items": _convert(node["items"], defs, f"{path}[]", depth + 1)}
    if node_type in PRIMITIVES:
        return {"type": node_type}
    raise _unsupported(path, node)
