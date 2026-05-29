from typing import Any

from pydantic import BaseModel


class ToolModel(BaseModel):
    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(**kwargs)
