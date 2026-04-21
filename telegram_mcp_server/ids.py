"""Opaque ID encoding/decoding for chats, messages, and media.

Chat IDs:
  c:{peer_id}              — regular chat/group/channel
  t:{supergroup_id}:{topic_id} — forum topic

Message IDs:
  m:{peer_id}:{msg_id}     — message in any chat (supergroup_id for topics)

Media IDs:
  mp:{peer_id}:{msg_id}    — photo/video/file attached to a message
  up:{user_id}             — user profile photo (current)
"""

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Chat IDs
# ---------------------------------------------------------------------------


def encode_chat(peer_id: int) -> str:
    return f"c:{peer_id}"


def encode_topic(supergroup_id: int, topic_id: int) -> str:
    return f"t:{supergroup_id}:{topic_id}"


@dataclass(frozen=True)
class ChatRef:
    peer_id: int
    topic_id: int | None = None  # None → regular chat; int → forum topic

    @property
    def is_topic(self) -> bool:
        return self.topic_id is not None

    def encode(self) -> str:
        if self.topic_id is not None:
            return encode_topic(self.peer_id, self.topic_id)
        return encode_chat(self.peer_id)


def decode_chat(chat_id: str) -> ChatRef:
    if chat_id.startswith("c:"):
        return ChatRef(peer_id=int(chat_id[2:]))
    if chat_id.startswith("t:"):
        _, sg, topic = chat_id.split(":", 2)
        return ChatRef(peer_id=int(sg), topic_id=int(topic))
    raise ValueError(f"Invalid chat ID: {chat_id!r}")


# ---------------------------------------------------------------------------
# Message IDs
# ---------------------------------------------------------------------------


def encode_message(peer_id: int, msg_id: int) -> str:
    return f"m:{peer_id}:{msg_id}"


@dataclass(frozen=True)
class MessageRef:
    peer_id: int
    msg_id: int

    def encode(self) -> str:
        return encode_message(self.peer_id, self.msg_id)


def decode_message(message_id: str) -> MessageRef:
    if not message_id.startswith("m:"):
        raise ValueError(f"Invalid message ID: {message_id!r}")
    _, peer, mid = message_id.split(":", 2)
    return MessageRef(peer_id=int(peer), msg_id=int(mid))


# ---------------------------------------------------------------------------
# Media IDs
# ---------------------------------------------------------------------------


def encode_message_media(peer_id: int, msg_id: int) -> str:
    return f"mp:{peer_id}:{msg_id}"


def encode_user_photo(user_id: int) -> str:
    return f"up:{user_id}"


@dataclass(frozen=True)
class MediaRef:
    kind: str  # "mp" or "up"
    peer_id: int
    msg_id: int | None = None  # only for "mp"


def decode_media(media_id: str) -> MediaRef:
    if media_id.startswith("mp:"):
        _, peer, mid = media_id.split(":", 2)
        return MediaRef(kind="mp", peer_id=int(peer), msg_id=int(mid))
    if media_id.startswith("up:"):
        return MediaRef(kind="up", peer_id=int(media_id[3:]))
    raise ValueError(f"Invalid media ID: {media_id!r}")
