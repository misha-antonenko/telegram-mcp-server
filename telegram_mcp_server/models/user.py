from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from telegram_mcp_server.ids import encode_user_photo

if TYPE_CHECKING:
    from telethon.tl.types import UserFull


@dataclass
class User:
    id: int
    name: str
    nickname: str | None  # Telegram @username
    bio: str | None
    profile_image_id: str | None  # opaque media ID, or None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "nickname": self.nickname,
            "bio": self.bio,
            "profile_image_id": self.profile_image_id,
        }

    @classmethod
    def from_full(cls, full: UserFull) -> User:
        """Build a User from a Telethon UserFull object."""
        user = full.users[0]
        first = getattr(user, "first_name", "") or ""
        last = getattr(user, "last_name", "") or ""
        name = (first + " " + last).strip() or str(user.id)
        nickname = getattr(user, "username", None)
        bio = getattr(full.full_user, "about", None) or None

        photo_id: str | None = None
        if getattr(user, "photo", None) is not None:
            photo_id = encode_user_photo(user.id)

        return cls(
            id=user.id,
            name=name,
            nickname=nickname,
            bio=bio,
            profile_image_id=photo_id,
        )
