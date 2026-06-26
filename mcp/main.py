"""FastMCP entry‑point for exposing Semantic‑Mapper tools.

This module creates a FastMCP server that registers the core utility
functions defined in :pymod:`agent.tools.tools`.  The functions are **not**
wrapped with LangChain's ``@tool`` decorator – we import the raw
implementations (e.g. ``fetch_vector_context_semantic``) and expose them
to MCP using FastMCP's own ``@tool`` decorator.

The server is started **only** when the environment variable
``mcp_enable`` is set to ``True`` (case‑insensitive).  This allows the
same Docker image to run either:

* **Streamlit only** – ``mcp_enable=False`` (default)
* **Streamlit + MCP** – ``mcp_enable=True``

The FastMCP server runs on ``0.0.0.0:8000`` and can be queried by any
MCP‑compatible client.
"""

import os
import sys

# ---------------------------------------------------------------------------
# Ensure the project root is on ``sys.path`` so that imports like
# ``from agent.tools.tools`` work when this file is executed directly
# (e.g. ``python mcp/main.py``). When the module is run via ``python -m`` the
# package layout already adds the root, but the explicit addition makes the
# script robust in both scenarios.
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Import FastMCP server and its ``tool`` decorator. If FastMCP is not
# installed we raise a clear error when the module is imported.
# Import FastMCP server class and the ``tool`` decorator. The ``tool``
# decorator lives in ``fastmcp.tools``; importing it directly from the top
# level raises an ``ImportError``.

from fastmcp import FastMCP
from fastmcp.tools import tool as mcp_tool


from agent.tools.tools import (
    fetch_vector_context_semantic,
    fetch_vector_context_fsdm,
    get_semantic_metadata_logic,
    get_fsdm_metadata_logic,
    list_tables_logic,
    query_db_logic,
    get_table_schema_logic,
    sample_table_data_logic,
    lg_get_instructions as get_instructions,  # alias for clarity
    list_fsdm_tables_logic,
    get_mapping_summary_logic,
    get_fsdm_summary_logic,
)

@mcp_tool
def fetch_vector_context_semantic_mcp(query: str, project_name: str) -> str:
    """MCP‑exposed wrapper for :func:`fetch_vector_context_semantic`."""
    return fetch_vector_context_semantic(query, project_name)

@mcp_tool
def fetch_vector_context_fsdm_mcp(query: str, project_name: str) -> str:
    """MCP‑exposed wrapper for :func:`fetch_vector_context_fsdm`."""
    return fetch_vector_context_fsdm(query, project_name)

@mcp_tool
def get_semantic_metadata_mcp(table_name: str, project_name: str) -> str:
    """MCP‑exposed wrapper for :func:`get_semantic_metadata_logic`."""
    return get_semantic_metadata_logic(table_name, project_name)

@mcp_tool
def get_fsdm_metadata_mcp(table_name: str, project_name: str) -> str:
    """MCP‑exposed wrapper for :func:`get_fsdm_metadata_logic`."""
    return get_fsdm_metadata_logic(table_name, project_name)

@mcp_tool
def list_tables_mcp(project_name: str, table_type: str = "all") -> str:
    """MCP‑exposed wrapper for :func:`list_tables_logic`."""
    return list_tables_logic(project_name, table_type)

@mcp_tool
def query_db_mcp(sql_query: str, project_name: str) -> str:
    """MCP‑exposed wrapper for :func:`query_db_logic`."""
    return query_db_logic(sql_query, project_name)

@mcp_tool
def get_table_schema_mcp(table_name: str, project_name: str) -> str:
    """MCP‑exposed wrapper for :func:`get_table_schema_logic`."""
    return get_table_schema_logic(table_name, project_name)

@mcp_tool
def sample_table_data_mcp(table_name: str, project_name: str, n: int = 5) -> str:
    """MCP‑exposed wrapper for :func:`sample_table_data_logic`."""
    return sample_table_data_logic(table_name, project_name, n)

@mcp_tool
def get_instructions_mcp(scope: str, project_name: str) -> str:
    """MCP‑exposed wrapper for :func:`get_instructions`."""
    return get_instructions(scope, project_name)

@mcp_tool
def list_fsdm_tables_mcp(project_name: str) -> str:
    """MCP‑exposed wrapper for :func:`list_fsdm_tables_logic`."""
    return list_fsdm_tables_logic(project_name)

@mcp_tool
def get_mapping_summary_mcp(tables: list, project_name: str) -> str:
    """MCP‑exposed wrapper for :func:`get_mapping_summary_logic`."""
    return get_mapping_summary_logic(project_name, tables)

@mcp_tool
def get_fsdm_summary_mcp(tables: list, project_name: str) -> str:
    """MCP‑exposed wrapper for :func:`get_fsdm_summary_logic`."""
    return get_fsdm_summary_logic(project_name, tables)

# Initialise the FastMCP server and register all tools.
server = FastMCP()
server.add_tool(fetch_vector_context_semantic_mcp)
server.add_tool(fetch_vector_context_fsdm_mcp)
server.add_tool(get_semantic_metadata_mcp)
server.add_tool(get_fsdm_metadata_mcp)
server.add_tool(list_tables_mcp)
server.add_tool(query_db_mcp)
server.add_tool(get_table_schema_mcp)
server.add_tool(sample_table_data_mcp)
server.add_tool(get_instructions_mcp)
server.add_tool(list_fsdm_tables_mcp)
server.add_tool(get_mapping_summary_mcp)
server.add_tool(get_fsdm_summary_mcp)

if __name__ == "__main__":
    # Run the server as an HTTP service.
    server.run(transport="http", host="0.0.0.0", port=8000)
