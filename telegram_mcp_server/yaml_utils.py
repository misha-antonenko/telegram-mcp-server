import functools
import io
from collections.abc import Callable
from typing import Any

import yaml


class _LiteralStr(str):
    pass


def _literal_representer(dumper: yaml.Dumper, data: str) -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


def _str_representer(dumper: yaml.Dumper, data: str) -> yaml.ScalarNode:
    if "\n" in data:
        block_style_compatible = "\n".join(line.rstrip() for line in data.split("\n"))
        return dumper.represent_scalar(
            "tag:yaml.org,2002:str", block_style_compatible, style="|"
        )
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


class _Dumper(yaml.Dumper):
    pass


_Dumper.add_representer(str, _str_representer)


def to_yaml(value: Any) -> str:
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


def returns_yaml[F: Callable[..., Any]](fn: F) -> F:
    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> str:
        result = await fn(*args, **kwargs)
        return to_yaml(result)

    return wrapper  # type: ignore[return-value]
