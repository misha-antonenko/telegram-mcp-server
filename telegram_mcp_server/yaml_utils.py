"""YAML serialization helpers for MCP tool return values.

Rules:
- Strings containing newlines use literal block style (|).
- All other scalar types use PyYAML defaults.
- Unicode is preserved (allow_unicode=True).
"""

import functools
import io
from collections.abc import Callable
from typing import Any, TypeVar

import yaml

F = TypeVar("F", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# Custom representer
# ---------------------------------------------------------------------------


class _LiteralStr(str):
    """Marker for strings that should use | block style."""


def _literal_representer(dumper: yaml.Dumper, data: str) -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


def _str_representer(dumper: yaml.Dumper, data: str) -> yaml.ScalarNode:
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


class _Dumper(yaml.Dumper):
    pass


_Dumper.add_representer(str, _str_representer)


def to_yaml(value: Any) -> str:
    """Serialize *value* to a YAML string."""
    buf = io.StringIO()
    yaml.dump(
        value,
        buf,
        Dumper=_Dumper,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


def returns_yaml(fn: F) -> F:
    """Decorator: serialize the return value of *fn* to YAML.

    The wrapped function must return a dict or list that is JSON-serializable.
    """

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> str:
        result = await fn(*args, **kwargs)
        return to_yaml(result)

    return wrapper  # type: ignore[return-value]
