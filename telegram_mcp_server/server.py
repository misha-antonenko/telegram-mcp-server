"""FastMCP server wiring."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date

from fastmcp import FastMCP
from fastmcp.server.auth import MultiAuth
from fastmcp.server.auth.providers.github import GitHubProvider
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from mcp.types import ImageContent

from telegram_mcp_server.client import disconnect, get_client
from telegram_mcp_server.settings import Settings, get_settings
from telegram_mcp_server.tools.chats import get_chats as _get_chats
from telegram_mcp_server.tools.chats import get_folders as _get_folders
from telegram_mcp_server.tools.chats import search_chats as _search_chats
from telegram_mcp_server.tools.media import get_image as _get_image
from telegram_mcp_server.tools.messages import count_messages as _count_messages
from telegram_mcp_server.tools.messages import get_message as _get_message
from telegram_mcp_server.tools.messages import get_messages as _get_messages
from telegram_mcp_server.tools.messages import search_messages as _search_messages
from telegram_mcp_server.tools.entities import get_entity as _get_entity
from telegram_mcp_server.tools.send import forward_message as _forward_message
from telegram_mcp_server.tools.send import send_message as _send_message
from telegram_mcp_server.tools.send import upload_attachment as _upload_attachment


@asynccontextmanager
async def _lifespan(_server: FastMCP):
    await get_client()
    try:
        yield
    finally:
        await disconnect()


def _configure_auth(settings: Settings):
    github_provider = None
    if settings.github_client_id and settings.github_client_secret:
        assert settings.mcp_domain, "MCP_DOMAIN must be set when using GitHub OAuth"
        domain = settings.mcp_domain
        base_url = (
            f"https://{domain}:{settings.mcp_external_port}"
            if settings.mcp_external_port
            else f"https://{domain}"
        )
        github_provider = GitHubProvider(
            client_id=settings.github_client_id,
            client_secret=settings.github_client_secret,
            base_url=base_url,
            jwt_signing_key=settings.github_jwt_signing_key,
        )

    token_verifier = None
    if auth_token := settings.mcp_auth_token:
        token_verifier = StaticTokenVerifier(
            tokens={auth_token: {"client_id": "mcp-client", "scopes": []}}
        )

    assert github_provider or token_verifier, (
        "Either GITHUB_CLIENT_ID/GITHUB_CLIENT_SECRET or MCP_AUTH_TOKEN must be set"
        " when running in HTTP transport mode"
    )

    if github_provider and token_verifier:
        # Override required_scopes=[] to prevent GitHubProvider's default ['user']
        # scope from being enforced against static tokens.
        return MultiAuth(
            server=github_provider, verifiers=[token_verifier], required_scopes=[]
        )
    return github_provider or token_verifier


mcp = FastMCP(
    name="telegram-mcp-server",
    lifespan=_lifespan,
    auth=_configure_auth(get_settings()),
)


@mcp.tool()
async def get_folders() -> str:
    """Return a YAML list of available chat folder names.

    The list always includes "all unarchived" and "archive", plus any
    custom folders the user has created in Telegram.
    Use these names as the *folder* argument of get_chats.
    """
    client = await get_client()
    return await _get_folders(client)


@mcp.tool()
async def get_chats(
    folder: str,
    page_idx: int = 0,
) -> str:
    """Return a paginated list of Telegram chats as YAML.

    Args:
        folder: Folder name. Always call get_folders first to obtain the list.
        page_idx: Zero-based page index (16 chats per page). The earlier the chat was last updated,
                  the higher the index.
    """
    client = await get_client()
    return await _get_chats(client, page_idx=page_idx, folder=folder)


@mcp.tool()
async def search_chats(query: str, limit: int = 16) -> str:
    """Search for chats by name substring (case-insensitive) across all dialogs.

    Args:
        query: Non-empty substring to match against chat names.
        limit: Maximum number of results to return (default 16).
    """
    client = await get_client()
    return await _search_chats(client, query=query, limit=limit)


@mcp.tool()
async def search_messages(
    query: str,
    page_idx: int = 0,
    since: date | None = None,
    until: date | None = None,
) -> str:
    """Search globally across all chats for messages containing a query string.

    For searching within a specific chat, use get_messages with search_query.

    Args:
        query: Non-empty search string.
        page_idx: Zero-based page index (16 messages per page).
        since: Only return messages from this date onwards (inclusive). Format: YYYY-MM-DD.
        until: Only return messages up to this date (exclusive). Format: YYYY-MM-DD.
    """
    client = await get_client()
    return await _search_messages(
        client,
        query=query,
        page_idx=page_idx,
        since=since,
        until=until,
    )


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
    since: date | None = None,
    page_idx: int = 0,
    search_query: str = "",
) -> str:
    """Return a paginated list of messages from a chat as YAML.

    Messages are ordered oldest-first.

    Args:
        chat_id: Opaque chat ID obtained from get_chats or search_chats.
        since: Only include messages from this date onwards (inclusive). Format: YYYY-MM-DD.
        page_idx: Zero-based page index (16 messages per page).
        search_query: Filter messages to those containing this text.
    """
    client = await get_client()
    return await _get_messages(
        client,
        chat_id=chat_id,
        since=since,
        page_idx=page_idx,
        search_query=search_query,
    )


@mcp.tool()
async def count_messages(
    chat_id: str,
    since: date | None = None,
    search_query: str = "",
) -> int:
    """Return the number of messages matching the given filters.

    The meaning of the arguments is the same as in get_messages.

    Args:
        chat_id: Opaque chat ID obtained from get_chats or search_chats.
        since: Only count messages from this date onwards (inclusive). Format: YYYY-MM-DD.
        search_query: Filter messages to those containing this text.
    """
    client = await get_client()
    return await _count_messages(
        client, chat_id=chat_id, since=since, search_query=search_query
    )


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
async def get_entity(entity_id: int) -> str:
    """Return information about a Telegram user, channel, or group as YAML.

    Args:
        entity_id: Numeric Telegram entity ID (user, channel, or group).

    Returns YAML with fields:
        id: Numeric ID
        type: "user", "channel", or "group"
        name: Display name
        username: @username if available
        description: Bio (users) or about text (channels/groups)
        profile_image_id: Opaque media ID for profile photo
    """
    client = await get_client()
    return await _get_entity(client, entity_id)


@mcp.tool()
async def upload_attachment(filename: str, data_base64: str) -> str:
    """Upload a file to the server's attachments directory so it can be sent via send_message.

    Args:
        filename: Basename of the file to create (no path separators allowed).
        data_base64: Base64-encoded file content.
    """
    settings = get_settings()
    return _upload_attachment(filename, data_base64, settings.attachments_dir)


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
        attachments: Optional list of filenames previously uploaded via upload_attachment.
        reply_to_message_id: Opaque message ID to reply to (from get_messages).
    """
    client = await get_client()
    settings = get_settings()
    return await _send_message(
        client,
        chat_id=chat_id,
        text=text,
        attachments=attachments,
        reply_to_message_id=reply_to_message_id,
        attachments_dir=settings.attachments_dir,
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
