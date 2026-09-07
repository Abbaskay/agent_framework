"""
registries/tool_registry.py — Tool registration.

Registering a tool used to take three coordinated edits: write the function,
import it into a name->callable dict, then hand-write ~25 lines of JSON schema
in a second file. Three places to forget one.

Now it takes one: decorate the function with @tool. The JSON schema is derived
from the signature, using Annotated[type, "..."] for parameter descriptions and
the docstring for the tool description.

    @tool
    def get_eta(order_id: Annotated[str, "The order ID, e.g. 'HZ001'."]) -> str:
        \"\"\"Get the estimated delivery time for an order.\"\"\"

Pass an explicit schema when the derivation is not expressive enough:

    @tool(schema={...})
"""

import inspect
from typing import Annotated, Any, Callable, get_args, get_origin, get_type_hints

# Populated by the @tool decorator at import time.
TOOL_REGISTRY: dict[str, Callable] = {}
SCHEMA_REGISTRY: dict[str, dict] = {}

_JSON_TYPES: dict[Any, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _json_type(annotation: Any) -> str:
    """Map a Python annotation to a JSON Schema type name."""
    return _JSON_TYPES.get(annotation, "string")


def _derive_schema(name: str, description: str, fn: Callable) -> dict:
    """Build an OpenAI-format function schema from a function signature."""
    signature = inspect.signature(fn)
    # include_extras=True keeps the Annotated metadata we use for param docs.
    hints = get_type_hints(fn, include_extras=True)

    properties: dict[str, dict] = {}
    required: list[str] = []

    for param_name, param in signature.parameters.items():
        if param_name == "self":
            continue

        annotation = hints.get(param_name, str)
        param_description = ""

        if get_origin(annotation) is Annotated:
            args = get_args(annotation)
            annotation = args[0]
            # First string in the metadata is the description.
            param_description = next(
                (a for a in args[1:] if isinstance(a, str)), ""
            )

        properties[param_name] = {
            "type": _json_type(annotation),
            "description": param_description,
        }

        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def tool(
    _fn: Callable | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
    schema: dict | None = None,
):
    """Register a function as an agent tool.

    Usable bare (@tool) or with arguments (@tool(description="...")).

    Args:
        name:        Override the tool name. Defaults to the function name.
        description: Override the tool description. Defaults to the docstring.
        schema:      Supply the full OpenAI function schema and skip derivation.
    """

    def decorator(fn: Callable) -> Callable:
        tool_name = name or fn.__name__
        tool_description = description or inspect.getdoc(fn) or ""

        if tool_name in TOOL_REGISTRY:
            raise ValueError(f"Tool '{tool_name}' is already registered.")

        TOOL_REGISTRY[tool_name] = fn
        SCHEMA_REGISTRY[tool_name] = schema or _derive_schema(
            tool_name, tool_description, fn
        )
        return fn

    return decorator(_fn) if _fn is not None else decorator


def get_schemas(tool_names: list[str]) -> list[dict]:
    """Return schemas for the named tools, skipping any that aren't registered."""
    return [SCHEMA_REGISTRY[n] for n in tool_names if n in SCHEMA_REGISTRY]


# Importing the tool modules is what runs the decorators and fills the
# registries. This import is at the bottom to avoid a circular import: the tool
# modules import `tool` from this module.
import tools  # noqa: E402,F401  (side-effect import — registers all tools)
