"""Main entry point."""

import logging

from fastmcp.server.auth import StaticTokenVerifier

from telegram_mcp_server.server import mcp
from telegram_mcp_server.settings import get_settings


def _configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    handler = logging.FileHandler("server.log", mode="a", encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("[%(asctime)s %(levelname)s %(name)s] %(message)s")
    )
    root.addHandler(handler)


def main() -> None:
    _configure_logging()
    settings = get_settings()
    if settings.mcp_transport == "stdio":
        mcp.run(transport="stdio")
    else:
        assert settings.mcp_auth_token, (
            "MCP_AUTH_TOKEN must be set when running in HTTP transport mode"
        )
        mcp.auth = StaticTokenVerifier(
            tokens={settings.mcp_auth_token: {"client_id": "mcp-client", "scopes": []}}
        )
        mcp.run(
            transport="streamable-http",
            host=settings.mcp_host,
            port=settings.mcp_port,
            stateless_http=True,
        )


if __name__ == "__main__":
    main()
