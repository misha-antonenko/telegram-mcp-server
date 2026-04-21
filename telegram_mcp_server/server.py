"""FastMCP server wiring."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastmcp import FastMCP
from mcp.types import ImageContent

from telegram_mcp_server.client import disconnect, get_client
from telegram_mcp_server.tools.chats import get_chats as _get_chats
from telegram_mcp_server.tools.media import get_image as _get_image
from telegram_mcp_server.tools.messages import get_message as _get_message
from telegram_mcp_server.tools.messages import get_messages as _get_messages
from telegram_mcp_server.tools.send import forward_message as _forward_message
from telegram_mcp_server.tools.send import send_message as _send_message
from telegram_mcp_server.tools.users import get_user as _get_user


@asynccontextmanager
async def _lifespan(server: FastMCP):  # noqa: ANN001
    await get_client()
    try:
        yield
    finally:
        await disconnect()


mcp = FastMCP(name="telegram-mcp-server", lifespan=_lifespan)


@mcp.tool()
async def get_chats(
    page_idx: int = 0,
    unread: bool | None = True,
    archived: bool | None = False,
) -> str:
    """Return a paginated list of Telegram chats as YAML.

    Args:
        page_idx: Zero-based page index (16 chats per page).
        unread: When True return only chats with unread messages;
                when False return only chats with no unread messages;
                when None do not filter by read status.
        archived: When True return archived chats; when False return non-archived;
                  when None return both.
    """
    client = await get_client()
    return await _get_chats(client, page_idx=page_idx, unread=unread, archived=archived)


@mcp.tool()
async def get_message(message_id: str) -> str:
    """Return a single message as YAML by its opaque message ID.

    Args:
        message_id: Opaque message ID obtained from get_messages (reply_to_message_id or id).
    """
    client = await get_client()
    return await _get_message(client, message_id=message_id)


@mcp.tool()
async def get_messages(
    chat_id: str,
    page_idx: int = 0,
) -> str:
    """Return a paginated list of messages from a chat as YAML.

    Args:
        chat_id: Opaque chat ID obtained from get_chats.
        page_idx: Zero-based page index (16 messages per page).
    """
    client = await get_client()
    return await _get_messages(client, chat_id=chat_id, page_idx=page_idx)


@mcp.tool()
async def get_image(media_id: str) -> ImageContent:
    """Fetch an image by its opaque media ID and return it as binary content.

    Args:
        media_id: Opaque media ID obtained from get_messages or get_user.
    """
    client = await get_client()
    result = await _get_image(client, media_id)
    return ImageContent(type="image", data=result["data"], mimeType=result["mime_type"])


@mcp.tool()
async def get_user(user_id: int) -> str:
    """Return information about a Telegram user as YAML.

    Args:
        user_id: Numeric Telegram user ID.
    """
    client = await get_client()
    return await _get_user(client, user_id)


@mcp.tool()
async def send_message(
    chat_id: str,
    text: str,
    attachments: list[str] | None = None,
    reply_to_message_id: str | None = None,
) -> str:
    """Send a Markdown-formatted message to a Telegram chat.

    Args:
        chat_id: Opaque chat ID obtained from get_chats.
        text: Message body in Markdown format.
        attachments: Optional list of local file paths to attach.
        reply_to_message_id: Opaque message ID to reply to (from get_messages).
    """
    client = await get_client()
    return await _send_message(
        client,
        chat_id=chat_id,
        text=text,
        attachments=attachments,
        reply_to_message_id=reply_to_message_id,
    )


@mcp.tool()
async def forward_message(message_id: str, to_chat_id: str) -> str:
    """Forward a message to another chat.

    Args:
        message_id: Opaque message ID obtained from get_messages.
        to_chat_id: Opaque destination chat ID obtained from get_chats.
    """
    client = await get_client()
    return await _forward_message(client, message_id=message_id, to_chat_id=to_chat_id)
