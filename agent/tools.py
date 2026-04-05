from langchain.tools import tool
from typing import Dict, Any, List
from logic.project_manager import ProjectManager
from langchain_community.utilities import SQLDatabase
import os

@tool
def fetch_vector_context(query: str, project_name: str) -> str:
    """
    Performs a semantic search on the project's knowledge base (PDFs, documents).
    Useful for finding business logic, documentation, and unstructured context.
    """
    from logic.vector_store import VectorStoreManager
    project_path = ProjectManager.get_project_path(project_name)
    vs_path = os.path.join(project_path, "vector_store")
    
    v_manager = VectorStoreManager(persist_directory=vs_path)
    v_manager.initialize_store()
    
    docs = v_manager.query(query, k=5)
    return "\n\n".join([doc.page_content for doc in docs])

@tool
def list_project_tables(project_name: str) -> str:
    """
    Lists all available tables in the project's SQLite database.
    Use this if you are unsure about table names before querying.
    """
    db_uri = ProjectManager.get_db_uri(project_name)
    db = SQLDatabase.from_uri(db_uri)
    try:
        tables = db.get_usable_table_names()
        return f"Available tables: {', '.join(tables)}"
    except Exception as e:
        return f"Error listing tables: {str(e)}"

@tool
def query_fsdm(sql_query: str, project_name: str) -> str:
    """
    Executes a SQL query against the FSDM (Financial Services Data Model) / ETL documentation tables.
    Use this to find specific table schemas, column descriptions, and technical mapping details 
    stored in the structured ETL/FSDM documents.
    Only use SELECT statements.
    """
    db_uri = ProjectManager.get_db_uri(project_name)
    db = SQLDatabase.from_uri(db_uri)
    
    try:
        # We try to filter out non-SELECT queries for safety
        if not sql_query.strip().lower().startswith("select"):
             return "Error: Only SELECT queries are allowed."
             
        return db.run(sql_query)
    except Exception as e:
        return f"Error executing SQL: {str(e)}. Hint: Use list_tables_tool to check table names if you get 'no such table'."

@tool
def query_mapping_schema(sql_query: str, project_name: str) -> str:
    """
    Executes a SQL query against the primary 'mapping_sheet' table.
    Use this to cross-reference other mappings, check for existing transformation patterns,
    or explore the overall mapping document structure.
    Only use SELECT statements.
    """
    db_uri = ProjectManager.get_db_uri(project_name)
    db = SQLDatabase.from_uri(db_uri)
    
    try:
        if not sql_query.strip().lower().startswith("select"):
             return "Error: Only SELECT queries are allowed."
             
        return db.run(sql_query)
    except Exception as e:
        return f"Error executing SQL: {str(e)}. Hint: Use list_tables_tool to check table names if you get 'no such table'."

def get_tools(project_name: str, log_callback=None):
    """Returns a list of tools partially applied with the project_name and integrated logging."""
    
    def _log(msg):
        if log_callback:
            log_callback(msg)

    # We use a wrapper to inject the project_name so the LLM doesn't have to guess it
    @tool
    def vector_tool(query: str) -> str:
        """Search unstructured documentation and PDFs for business logic and column definitions."""
        _log(f"🔍 [Tool: Vector Search] Query: {query}")
        res = fetch_vector_context.invoke({"query": query, "project_name": project_name})
        _log(f"✅ [Tool: Vector Search] Found documentation context.")
        return res

    @tool
    def fsdm_tool(sql_query: str) -> str:
        """Query structured FSDM/ETL documentation tables for precise schemas and join keys."""
        _log(f"🛠️ [Tool: SQL FSDM] Executing: {sql_query}")
        res = query_fsdm.invoke({"sql_query": sql_query, "project_name": project_name})
        if res.startswith("Error"):
            _log(f"❌ [Tool: SQL FSDM] Query failed.")
        else:
            _log(f"✅ [Tool: SQL FSDM] Query successful.")
        return res

    @tool
    def mapping_tool(sql_query: str) -> str:
        """Query the main mapping sheet table to see how other similar columns were mapped."""
        _log(f"🛠️ [Tool: SQL Mapping] Executing: {sql_query}")
        res = query_mapping_schema.invoke({"sql_query": sql_query, "project_name": project_name})
        if res.startswith("Error"):
            _log(f"❌ [Tool: SQL Mapping] Query failed.")
        else:
            _log(f"✅ [Tool: SQL Mapping] Query successful.")
        return res

    @tool
    def list_tables_tool() -> str:
        """List all available tables in the database. Use this if you get 'no such table' errors."""
        _log(f"📋 [Tool: List Tables] Fetching database schema...")
        res = list_project_tables.invoke({"project_name": project_name})
        _log(f"✅ [Tool: List Tables] Tables retrieved.")
        return res

    return [vector_tool, fsdm_tool, mapping_tool, list_tables_tool]
