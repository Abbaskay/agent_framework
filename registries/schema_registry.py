"""
registries/schema_registry.py — Tool schemas.

This file used to hold ~200 lines of hand-written JSON Schema kept manually in
sync with the tool functions. Schemas are now derived from each function's
signature by the @tool decorator in `tool_registry.py`, so the two can no
longer drift apart.

Kept as a re-export so existing imports keep working:

    from registries.schema_registry import SCHEMA_REGISTRY
"""

from registries.tool_registry import SCHEMA_REGISTRY, get_schemas

__all__ = ["SCHEMA_REGISTRY", "get_schemas"]
