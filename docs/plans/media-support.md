# Media support: images, image files, text files, voice

## Goal

Let the model consume images (photos and images sent as files), text files, and voice messages.

## Interfaces

### Message YAML (get_messages, get_message, search_messages)

| Telegram media | Fields |
|---|---|
| Photo | `text` (caption), `image: mp:…` |
| Document with `image/*` MIME type | `text` (caption), `image: mp:…` |
| Voice message | `text` (caption), `voice: <transcript>` |
| Audio / video | unchanged: `audio: mp:…` / `video: mp:…` |
| Sticker | unchanged |
| Any other document | `text` (caption), `file: mp:…`, `file_name` (if known) |

Images are not inlined; the model fetches them on demand.

### Tools

- `get_image(media_id)`: rejects non-image media before downloading. Decodes with Pillow; passes through JPEG/PNG/GIF/WEBP whose longest side ≤ `IMAGE_MAX_SIDE_PX` (default 1568), otherwise downscales and re-encodes (JPEG stays JPEG, everything else becomes PNG).
- `get_text_file(media_id)` (new): returns the file decoded as UTF-8. Fails if the file exceeds `TEXT_FILE_MAX_BYTES` (default 256 KiB) or is not valid UTF-8.

### Transcription

`messages.TranscribeAudioRequest`, polled every `TRANSCRIPTION_POLL_INTERVAL_SECONDS` while `pending`, up to `TRANSCRIPTION_TIMEOUT_SECONDS`. Voice messages of a page are transcribed concurrently. Telegram errors and timeouts propagate.

## Modules

- `models/media.py`: classification of Telethon media into a `MediaCategory` enum, shared by the message model and the tools.
- `tools/transcription.py`: voice transcription.
- `tools/images.py`: Pillow normalization.
- `tools/media.py`: `get_image`, `get_text_file`.

## Status

- [ ] Media classification + message model
- [ ] Voice transcription
- [ ] Image normalization and type check in get_image
- [ ] get_text_file
- [ ] README, deploy, live test
