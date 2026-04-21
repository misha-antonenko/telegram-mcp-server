# Deployment

## Overview

The server is packaged as a Docker image and orchestrated with Docker Compose. It runs in HTTP transport mode (FastMCP's `streamable-http`) and listens on port 8000 inside the container, which is mapped to the host.

## Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Builds the server image using `uv` for dependency installation |
| `docker-compose.yml` | Declares the service, port mapping, and env-file reference |
| `.env` | Runtime secrets (gitignored) |
| `.env.example` | Template documenting all required variables |

## Quick start

1. Copy and fill in the environment file:
   ```bash
   cp .env.example .env
   # Edit .env: set API_ID, API_HASH, SESSION_STRING, MCP_AUTH_TOKEN
   ```

2. Generate a secure token (see `rfcs/02_auth.md`).

3. Start the stack:
   ```bash
   docker compose up -d
   ```

4. The MCP endpoint is reachable at `http://<host>:8000/mcp`.

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `API_ID` | Yes | Telegram API ID from my.telegram.org |
| `API_HASH` | Yes | Telegram API hash from my.telegram.org |
| `SESSION_STRING` | Yes | Telethon string session (run `session_string_generator.py` once on the host) |
| `MCP_AUTH_TOKEN` | Yes | Shared Bearer token for MCP client authentication |

## HTTPS

TLS is terminated by a [Caddy](https://caddyserver.com/) reverse proxy running as a sidecar container. Caddy obtains and renews Let's Encrypt certificates automatically via the ACME HTTP-01 challenge. The app container is not exposed directly to the network — only Caddy's ports 80 and 443 are published.

### Prerequisites

- A DNS A record for `MCP_DOMAIN` pointing to the server's public IP.
- Ports 80 and 443 open in the firewall (port 80 is required only for the ACME challenge).

### Variables

| Variable | Description |
|----------|-------------|
| `MCP_DOMAIN` | Fully-qualified domain name (e.g. `mcp.example.com`). |

Caddy reads `MCP_DOMAIN` from the environment via `{$MCP_DOMAIN}` in `Caddyfile`.

### Certificate storage

Caddy stores certificates in the `caddy_data` named Docker volume so they survive container restarts and upgrades.

## Volumes

No persistent volumes are needed when `SESSION_STRING` is used (string sessions are stateless). If a file-based session is preferred, mount a named volume to `/app` and provide `SESSION_NAME` instead.

## Image

The image uses the official Python 3.13 slim base. `uv` installs all dependencies from the lockfile for reproducible builds. The image runs as a non-root user for security.

## Transport mode

`main.py` detects whether it is running in HTTP mode by checking the `MCP_TRANSPORT` environment variable (default: `http`). In HTTP mode FastMCP's `streamable-http` transport is used. The server binds to `0.0.0.0:8000`.
