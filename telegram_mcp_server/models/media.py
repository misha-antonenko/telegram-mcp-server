from __future__ import annotations

from enum import StrEnum

from telethon.tl.types import (
    Document,
    DocumentAttributeAudio,
    DocumentAttributeFilename,
    DocumentAttributeSticker,
    DocumentAttributeVideo,
    MessageMediaDocument,
    MessageMediaPhoto,
    MessageMediaWebPage,
)


class MediaCategory(StrEnum):
    IMAGE = "image"
    VOICE = "voice"
    AUDIO = "audio"
    VIDEO = "video"
    STICKER = "sticker"
    FILE = "file"
    OTHER = "other"


def classify_media(media: object) -> MediaCategory | None:
    if media is None or isinstance(media, MessageMediaWebPage):
        return None
    if isinstance(media, MessageMediaPhoto):
        return MediaCategory.IMAGE
    if isinstance(media, MessageMediaDocument) and isinstance(media.document, Document):
        return _classify_document(media.document)
    return MediaCategory.OTHER


def _classify_document(document: Document) -> MediaCategory:
    attributes = document.attributes
    if any(isinstance(a, DocumentAttributeSticker) for a in attributes):
        return MediaCategory.STICKER
    for attribute in attributes:
        if isinstance(attribute, DocumentAttributeAudio):
            return MediaCategory.VOICE if attribute.voice else MediaCategory.AUDIO
        if isinstance(attribute, DocumentAttributeVideo):
            return MediaCategory.VIDEO
    if document.mime_type.startswith("image/"):
        return MediaCategory.IMAGE
    return MediaCategory.FILE


def get_document_file_name(document: Document) -> str | None:
    names = [a.file_name for a in document.attributes if isinstance(a, DocumentAttributeFilename)]
    return names[0] if names else None
