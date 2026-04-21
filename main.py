from fastmcp.server.auth import StaticTokenVerifier

from telegram_mcp_server.server import mcp
from telegram_mcp_server.settings import get_settings


def main() -> None:
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
        )


if __name__ == "__main__":
    main()
