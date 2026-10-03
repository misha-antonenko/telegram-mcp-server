from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telethon.tl.types import (
    Document,
    DocumentAttributeAudio,
    MessageMediaDocument,
    PeerUser,
)
from telethon.tl.types.messages import TranscribedAudio

from telegram_mcp_server.models.message import Message
from telegram_mcp_server.tools.transcription import attach_voice_transcripts


def _make_tl_message(msg_id: int, *, is_voice: bool) -> MagicMock:
    document = Document(
        id=1,
        access_hash=0,
        file_reference=b"",
        date=None,
        mime_type="audio/ogg",
        size=1,
        dc_id=1,
        attributes=[DocumentAttributeAudio(duration=1, voice=is_voice)],
    )
    tl_message = MagicMock()
    tl_message.id = msg_id
    tl_message.peer_id = PeerUser(user_id=5)
    tl_message.media = MessageMediaDocument(document=document)
    return tl_message


def _transcribed(text: str, *, pending: bool) -> TranscribedAudio:
    return TranscribedAudio(transcription_id=1, text=text, pending=pending)


@pytest.fixture(autouse=True)
def fast_settings():
    settings = MagicMock(transcription_timeout_seconds=0.05, transcription_poll_interval_seconds=0)
    with patch("telegram_mcp_server.tools.transcription.get_settings", return_value=settings):
        yield


@pytest.mark.parametrize(
    "responses",
    [
        [_transcribed("hello", pending=False)],
        [
            _transcribed("", pending=True),
            _transcribed("hel", pending=True),
            _transcribed("hello", pending=False),
        ],
    ],
    ids=["immediate", "after_polling"],
)
async def test_voice_gets_final_transcript(responses):
    client = AsyncMock(side_effect=responses)
    tl_messages = [_make_tl_message(1, is_voice=True), _make_tl_message(2, is_voice=False)]
    messages = [Message(id=str(m.id), timestamp="", text="") for m in tl_messages]

    await attach_voice_transcripts(client, messages, tl_messages)

    assert [m.voice for m in messages] == ["hello", None]
    assert client.await_count == len(responses)
    assert {call.args[0].msg_id for call in client.await_args_list} == {1}


async def test_pending_transcription_times_out():
    client = AsyncMock(return_value=_transcribed("", pending=True))
    tl_messages = [_make_tl_message(1, is_voice=True)]
    messages = [Message(id="1", timestamp="", text="")]

    with pytest.raises(TimeoutError, match="TRANSCRIPTION_TIMEOUT_SECONDS"):
        await attach_voice_transcripts(client, messages, tl_messages)
