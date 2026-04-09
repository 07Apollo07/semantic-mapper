from langchain.tools import tool
from typing import Dict, Any, List
from logic.project_manager import ProjectManager
from langchain_community.utilities import SQLDatabase
import os
import pandas as pd
import sqlite3

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

@tool
def get_table_schema(table_name: str, project_name: str) -> str:
    """
    Returns the CREATE TABLE statement for a specific table.
    Use this to see the exact columns and types for a table.
    """
    db_uri = ProjectManager.get_db_uri(project_name)
    db = SQLDatabase.from_uri(db_uri)
    try:
        return db.get_table_info([table_name])
    except Exception as e:
        return f"Error fetching schema: {str(e)}"

@tool
def sample_table_data(table_name: str, project_name: str, n: int = 5) -> str:
    """
    Returns the first N rows of a table to help understand the data format.
    Use this if you are unsure about column values or formats.
    """
    db_uri = ProjectManager.get_db_uri(project_name)
    db = SQLDatabase.from_uri(db_uri)
    try:
        return db.run(f"SELECT * FROM \"{table_name}\" LIMIT {n}")
    except Exception as e:
        return f"Error sampling data: {str(e)}"

@tool
def get_business_schema_summary(project_name: str) -> str:
    """
    Analyzes the mapping metadata and FSDM tables to extract a structured summary 
    of the actual business tables and columns mentioned in the rows.
    Returns a format like:
    Table Name:
     - Column 1
     - Column 2
    """
    db_uri = ProjectManager.get_db_uri(project_name)
    db = SQLDatabase.from_uri(db_uri)
    
    summary = []
    
    # 1. Analyze mapping_sheet
    try:
        df_map = pd.read_sql_query("SELECT * FROM mapping_sheet", sqlite3.connect(ProjectManager.get_db_path(project_name)))
        if not df_map.empty:
            summary.append("--- Business Entities from Mapping Sheet ---")
            # Heuristically find source/target table and column columns
            # We'll look for keywords in column names
            tbl_cols = [c for c in df_map.columns if "tbl" in c.lower() or "table" in c.lower()]
            col_cols = [c for c in df_map.columns if "col" in c.lower() or "field" in c.lower()]
            
            entities = {}
            for _, row in df_map.iterrows():
                for t_col in tbl_cols:
                    t_name = str(row[t_col]).strip()
                    if not t_name or t_name.lower() == "nan" or t_name.lower() == "none": continue
                    if t_name not in entities: entities[t_name] = set()
                    for c_col in col_cols:
                        c_name = str(row[c_col]).strip()
                        if not c_name or c_name.lower() == "nan" or c_name.lower() == "none": continue
                        entities[t_name].add(c_name)
            
            for t, cols in entities.items():
                summary.append(f"\nTable: {t}")
                for c in sorted(list(cols)):
                    summary.append(f" - {c}")
    except Exception as e:
        summary.append(f"Error mapping sheet: {str(e)}")

    # 2. Analyze FSDM tables
    try:
        tables = db.get_usable_table_names()
        fsdm_tables = [t for t in tables if "fsdm" in t.lower() or "etl" in t.lower()]
        if fsdm_tables:
            summary.append("\n--- Business Entities from FSDM/ETL Documentation ---")
            for ft in fsdm_tables:
                df_fsdm = pd.read_sql_query(f"SELECT * FROM {ft}", sqlite3.connect(ProjectManager.get_db_path(project_name)))
                # Similar heuristic
                tbl_cols = [c for c in df_fsdm.columns if "tbl" in c.lower() or "table" in c.lower()]
                col_cols = [c for c in df_fsdm.columns if "col" in c.lower() or "field" in c.lower()]
                
                entities = {}
                for _, row in df_fsdm.iterrows():
                    for t_col in tbl_cols:
                        t_name = str(row[t_col]).strip()
                        if not t_name or t_name.lower() == "nan" or t_name.lower() == "none": continue
                        if t_name not in entities: entities[t_name] = set()
                        for c_col in col_cols:
                            c_name = str(row[c_col]).strip()
                            if not c_name or c_name.lower() == "nan" or c_name.lower() == "none": continue
                            entities[t_name].add(c_name)
                
                for t, cols in entities.items():
                    summary.append(f"\nTable: {t}")
                    for c in sorted(list(cols)):
                        summary.append(f" - {c}")
    except Exception as e:
        summary.append(f"Error FSDM: {str(e)}")
        
    if not summary:
        return "No business entities could be extracted from metadata."
        
    return "\n".join(summary)

@tool
def search_documentation(query_term: str, project_name: str) -> str:
    """
    Searches all FSDM/ETL/Documentation tables for a specific term (e.g. table name or column name).
    Returns all rows where the term is found. 
    Use this to 'filter' the documentation sheets to reach a specific table's metadata.
    """
    db_uri = ProjectManager.get_db_uri(project_name)
    db = SQLDatabase.from_uri(db_uri)
    
    try:
        tables = db.get_usable_table_names()
        # Filter for tables specifically prefixed with fsdm_etl_ as per user instruction
        doc_tables = [t for t in tables if t.lower().startswith("fsdm_etl_")]
        
        results = []
        for table in doc_tables:
            # We use a simple LIKE search on all text columns
            columns_info = db.run(f"PRAGMA table_info(\"{table}\")")
            import ast
            cols = ast.literal_eval(columns_info)
            col_names = [c[1] for c in cols]
            
            # Search for the term in all columns, limiting to 10 rows per table for conciseness
            where_clauses = [f"\"{c}\" LIKE '%{query_term}%'" for c in col_names]
            sql = f"SELECT * FROM \"{table}\" WHERE {' OR '.join(where_clauses)} LIMIT 10"
            
            try:
                res = db.run(sql)
                if res and res != "[]":
                    results.append(f"\n--- {table} ---")
                    results.append(res)
            except:
                continue
                
        if not results:
            return f"No fsdm_etl_ documentation found for term: {query_term}"
            
        return "\n".join(results)
    except Exception as e:
        return f"Error searching documentation: {str(e)}"

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

    @tool
    def schema_tool(table_name: str) -> str:
        """Get the detailed schema (CREATE TABLE) for a specific table."""
        _log(f"📋 [Tool: Schema] Fetching schema for table: {table_name}")
        res = get_table_schema.invoke({"table_name": table_name, "project_name": project_name})
        _log(f"✅ [Tool: Schema] Schema retrieved.")
        return res

    @tool
    def sample_data_tool(table_name: str, n: int = 5) -> str:
        """Sample the first {n} rows of a table to see the data format."""
        _log(f"📋 [Tool: Sample Data] Sampling {n} rows from: {table_name}")
        res = sample_table_data.invoke({"table_name": table_name, "project_name": project_name, "n": n})
        _log(f"✅ [Tool: Sample Data] Data sampled.")
        return res

    @tool
    def business_schema_tool() -> str:
        """Summarize the actual business tables and columns mentioned in the mapping/FSDM metadata rows."""
        _log(f"📋 [Tool: Business Schema] Analyzing metadata rows for business logic...")
        res = get_business_schema_summary.invoke({"project_name": project_name})
        _log(f"✅ [Tool: Business Schema] Business schema summarized.")
        return res

    return [vector_tool, fsdm_tool, mapping_tool, list_tables_tool, schema_tool, sample_data_tool, business_schema_tool]
