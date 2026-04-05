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
        return f"Error executing SQL: {str(e)}"

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
             
        # The table name in SQLite for the mapping sheet is expected to be 'mapping_sheet'
        # if the user followed the default or we forced it during ingestion.
        return db.run(sql_query)
    except Exception as e:
        return f"Error executing SQL: {str(e)}"

def get_tools(project_name: str):
    """Returns a list of tools partially applied with the project_name."""
    
    # We use a wrapper to inject the project_name so the LLM doesn't have to guess it
    @tool
    def vector_tool(query: str) -> str:
        """Search unstructured documentation and PDFs."""
        return fetch_vector_context.invoke({"query": query, "project_name": project_name})

    @tool
    def fsdm_tool(sql_query: str) -> str:
        """Query structured FSDM/ETL documentation tables."""
        return query_fsdm.invoke({"sql_query": sql_query, "project_name": project_name})

    @tool
    def mapping_tool(sql_query: str) -> str:
        """Query the main mapping sheet table."""
        return query_mapping_schema.invoke({"sql_query": sql_query, "project_name": project_name})

    return [vector_tool, fsdm_tool, mapping_tool]
