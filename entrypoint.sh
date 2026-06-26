#!/usr/bin/env bash

# ---------------------------------------------------------------------------
# Entrypoint for the Semantic‑Mapper Docker image.
#
# * Starts the FastMCP server **only** when the environment variable
#   ``mcp_enable`` (case‑insensitive) is set to "true".
# * Starts the Streamlit UI.
# * Both processes run in the background and the script waits for the first
#   one to exit, propagating its exit code.  This keeps the container alive
#   while both services are healthy and ensures the container stops if either
#   crashes.
# ---------------------------------------------------------------------------

set -euo pipefail   # fail fast, treat unset vars as errors

# Ensure the project root (/app) is on the Python import path.  This fixes
# "No module named mcp.main" when the virtual environment does not automatically
# include the working directory.
export PYTHONPATH="/app"

# -------------------------------------------------
# Helper: start FastMCP if enabled
# -------------------------------------------------
start_mcp() {
  echo "[entrypoint] MCP enabled – launching FastMCP server on port 8000..."
  # ``python -m mcp.main`` runs the ``__main__`` block which calls
  # ``server.run(host='0.0.0.0', port=8000)``.
  python /app/mcp/main.py &
  MCP_PID=$!
}

# -------------------------------------------------
# Helper: start Streamlit (foreground)
# -------------------------------------------------
start_streamlit() {
  echo "[entrypoint] Starting Streamlit UI on 0.0.0.0:8501"
  streamlit run app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 &
  STREAMLIT_PID=$!
}

# -----------------------------------------------------------------
# Main flow
# -----------------------------------------------------------------
if [[ "${mcp_enable,,}" == "true" ]]; then
  start_mcp
else
  echo "[entrypoint] MCP disabled – only Streamlit will run."
fi

start_streamlit

# Wait for the first background process to exit (so the container stops on
# failure of either service). ``wait -n`` is POSIX‑compatible in recent Bash.
wait -n
EXIT_CODE=$?
echo "[entrypoint] Service exited with code $EXIT_CODE – shutting down."
exit $EXIT_CODE
