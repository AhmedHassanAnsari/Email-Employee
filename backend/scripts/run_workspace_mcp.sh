#!/usr/bin/env bash
# Launch taylorwilsdon/google_workspace_mcp in EXTERNAL-PROVIDER mode.
#
# In this mode workspace-mcp is a pure resource server: it validates the
# ya29.* Google access tokens WE mint (via Google's userinfo API) and routes by
# the email in the token. It does NOT run its own consent flow — OUR FastAPI
# (/oauth/google/start) owns that and stores refresh tokens in Postgres.
#
# Reads OAUTH_GOOGLE_CLIENT_ID/SECRET from .env and maps them to the
# GOOGLE_OAUTH_CLIENT_ID/SECRET names workspace-mcp expects. Run from backend/:
#   bash scripts/run_workspace_mcp.sh
set -euo pipefail

# Load .env from the repo root (one level up from backend/).
ENV_FILE="$(dirname "$0")/../../.env"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

# Map our env names to what workspace-mcp reads.
export GOOGLE_OAUTH_CLIENT_ID="${OAUTH_GOOGLE_CLIENT_ID:-${GOOGLE_OAUTH_CLIENT_ID:-}}"
export GOOGLE_OAUTH_CLIENT_SECRET="${OAUTH_GOOGLE_CLIENT_SECRET:-${GOOGLE_OAUTH_CLIENT_SECRET:-}}"

# External-provider mode requires OAuth 2.1 to be enabled too.
export MCP_ENABLE_OAUTH21=true
export EXTERNAL_OAUTH21_PROVIDER=true
export WORKSPACE_MCP_PORT="${WORKSPACE_MCP_PORT:-8000}"
# Local dev over http (Google userinfo validation still uses https upstream).
export OAUTHLIB_INSECURE_TRANSPORT="${OAUTHLIB_INSECURE_TRANSPORT:-1}"

exec uvx workspace-mcp --transport streamable-http --tools gmail
