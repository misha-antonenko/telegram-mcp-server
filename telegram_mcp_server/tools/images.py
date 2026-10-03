from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image as PillowImage

_PASSTHROUGH_FORMATS = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "GIF": "image/gif",
    "WEBP": "image/webp",
}


@dataclass(frozen=True, slots=True)
class EncodedImage:
    mime_type: str
    data: bytes


def normalize_image(data: bytes, max_side_px: int) -> EncodedImage:
    with PillowImage.open(io.BytesIO(data)) as image:
        image_format = image.format
        if image_format in _PASSTHROUGH_FORMATS and max(image.size) <= max_side_px:
            return EncodedImage(mime_type=_PASSTHROUGH_FORMATS[image_format], data=data)
        image.thumbnail((max_side_px, max_side_px))
        if image_format == "JPEG":
            return _encode(image.convert("RGB"), "JPEG")
        return _encode(image, "PNG")


def _encode(image: PillowImage.Image, image_format: str) -> EncodedImage:
    buffer = io.BytesIO()
    image.save(buffer, format=image_format)
    return EncodedImage(mime_type=_PASSTHROUGH_FORMATS[image_format], data=buffer.getvalue())
