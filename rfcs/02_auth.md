# Authentication

## Overview

The server exposes an HTTP MCP endpoint. Every request must carry a Bearer token in the `Authorization` header. The server validates that token using FastMCP's built-in `StaticTokenVerifier`.

## Mechanism

`StaticTokenVerifier` receives a map of `{ token_string → metadata }` at startup. On each request FastMCP extracts the `Authorization: Bearer <token>` header and calls `StaticTokenVerifier.verify_token(token)`. If the token is not in the map (or has expired), the server returns HTTP 401 and the request is rejected before any tool logic runs.

## Configuration

A single shared secret token is sufficient for the use-case of trusted callers. The token is supplied via the `MCP_AUTH_TOKEN` environment variable. `MCP_AUTH_TOKEN` is **required** when running in HTTP transport mode and ignored in stdio mode. At startup the server reads this variable and builds the token map:

```python
StaticTokenVerifier(tokens={settings.mcp_auth_token: {"client_id": "mcp-client", "scopes": []}})
```

## Secret management

- `MCP_AUTH_TOKEN` must **never** be committed to Git.
- In local development it goes into `.env` (already in `.gitignore`).
- In Docker deployments it is injected via a `.env` file or Docker secrets (see `rfcs/03_deployment.md`).
- `.env.example` documents the variable with a placeholder value.

## Generating a token

Any sufficiently random string is acceptable. The recommended way:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Client usage

MCP clients must pass the token as a Bearer token:

```
Authorization: Bearer <MCP_AUTH_TOKEN value>
```

In Claude Desktop / MCP client configuration this is typically expressed as:

```json
{
  "mcpServers": {
    "telegram": {
      "url": "http://<host>:8000/mcp",
      "headers": { "Authorization": "Bearer <token>" }
    }
  }
}
```
