from langchain.tools import tool
from typing import Dict, Any, List
from logic.project_manager import ProjectManager
from langchain_community.utilities import SQLDatabase
import os
from logic.project_manager import ProjectManager
import pandas as pd
import sqlite3
import ast

# VS
def fetch_vector_context_semantic(query: str, project_name: str) -> str:
    """Performs Vector search on the Semantic knowledge base."""
    from logic.vector_store import VectorStoreManager
    project_path = ProjectManager.get_project_path(project_name)
    vs_path = os.path.join(project_path, "vector_store")
    v_manager = VectorStoreManager(persist_directory=vs_path)
    docs = v_manager.query(query, k=5, collection_name="semantic")
    return "\n\n".join([doc.page_content for doc in docs])

def fetch_vector_context_fsdm(query: str, project_name: str) -> str:
    """Performs Vector search on the project FSDM knowledge base."""
    from logic.vector_store import VectorStoreManager
    project_path = ProjectManager.get_project_path(project_name)
    vs_path = os.path.join(project_path, "vector_store")
    v_manager = VectorStoreManager(persist_directory=vs_path)
    docs = v_manager.query(query, k=5, collection_name="fsdm")
    return "\n\n".join([doc.page_content for doc in docs])
# Semantic
def get_semantic_metadata_logic(table_name: str, project_name: str) -> str:
    """Finds metadata for a specific semantic table."""
    from logic.project_manager import ProjectManager
    meta = ProjectManager.load_metadata(project_name)
    for item in meta.get("kb_inventory", []):
        for s_name, s_info in item.get("sheets", {}).items():
            if f"semantic_{s_name.lower()}" == table_name:
                return s_info.get("metadata", "No metadata found.")
    return "Table not found in semantic knowledge base."


# FSDM
def get_fsdm_metadata_logic(table_name: str, project_name: str) -> str:
    """Finds metadata for a specific FSDM table."""
    from logic.project_manager import ProjectManager
    meta = ProjectManager.load_metadata(project_name)
    for item in meta.get("fsdm_inventory", []):
        for s_name, s_info in item.get("sheets", {}).items():
            if f"fsdm_etl_{s_name.lower()}" == table_name:
                return s_info.get("metadata", "No metadata found.")
    return "Table not found in FSDM knowledge base."

# Common
def list_tables_logic(project_name: str, table_type: str = "all") -> str:
    """Lists tables in the project's SQLite database, optionally filtered by type."""
    db_uri = ProjectManager.get_db_uri(project_name)
    db = SQLDatabase.from_uri(db_uri)
    try:
        all_tables = db.get_usable_table_names()
        if table_type == "semantic":
            tables = [t for t in all_tables if t.lower().startswith("semantic_")]
            return f"Available Semantic tables: {', '.join(tables)}"
        elif table_type == "fsdm":
            tables = [t for t in all_tables if t.lower().startswith("fsdm_etl_")]
            return f"Available FSDM tables: {', '.join(tables)}"
        else:
            return f"Available tables: {', '.join(all_tables)}"
    except Exception as e:
        return f"Error listing tables: {str(e)}"
    

def query_db_logic(sql_query: str, project_name: str) -> str:
    """
    Executes a SQL query against the FSDM (Financial Services Data Model) / ETL documentation tables.
    Use this to find specific table schemas, column descriptions, and technical mapping details 
    stored in the structured ETL/FSDM documents.
    Only use SELECT statements.
    """
    db_uri = ProjectManager.get_db_uri(project_name)
    db = SQLDatabase.from_uri(db_uri)
    try:
        if not sql_query.strip().lower().startswith("select"):
             return "Error: Only SELECT queries are allowed."
        return db.run(sql_query)
    except Exception as e:
        return f"Error executing SQL: {str(e)}"


def query_full_db_data(sql_query: str, project_name: str) -> str:
    """
    Executes a SQL SELECT query against the project database using raw sqlite3.
    This bypasses LangChain's default result truncation.
    """
    db_path = ProjectManager.get_db_path(project_name)
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        headers = [description[0] for description in cursor.description]
        return f"Headers: {headers}\nRows: {rows}"
    except Exception as e:
        return f"Error executing query: {str(e)}"
    finally:
        conn.close()


def get_table_schema_logic(table_name: str, project_name: str) -> str:
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


def sample_table_data_logic(table_name: str, project_name: str, n: int = 5) -> str:
    """
    Returns the first N rows of a table in a raw format: 
    First line contains headers as a tuple, 
    Second line contains data as a list of tuples.
    """
    db_path = ProjectManager.get_db_path(project_name)
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(f'SELECT * FROM "{table_name}" LIMIT {n}')
        rows = cursor.fetchall()
        headers = tuple([description[0] for description in cursor.description])

        return f"Headers: {headers}\nRows: {rows}"
    except Exception as e:
        return f"Error sampling data from {table_name}: {str(e)}"
    finally:
        conn.close()

# Unused
def list_fsdm_tables_logic(project_name: str) -> str:
    """
    Lists available tables in the project's SQLite database that start with 'fsdm_etl_'.
    """
    db_uri = ProjectManager.get_db_uri(project_name)
    db = SQLDatabase.from_uri(db_uri)
    try:
        all_tables = db.get_usable_table_names()
        fsdm_tables = [t for t in all_tables if t.lower().startswith("fsdm_etl_")]
        return f"Available FSDM tables: {', '.join(fsdm_tables)}"
    except Exception as e:
        return f"Error listing FSDM tables: {str(e)}"

def get_mapping_summary_logic(project_name: str, tables: List[str]) -> str:
    """
    Analyzes the 'mapping_sheet' table to find metadata matching the provided business table names.
    Returns mapping metadata summaries for those specific tables.
    """
    db_path = ProjectManager.get_db_path(project_name)
    conn = sqlite3.connect(db_path)
    summary = []
    
    try:
        df_map = pd.read_sql_query("SELECT * FROM mapping_sheet", conn)
        summary.append(f"--- Mapping Metadata for tables: {', '.join(tables)} ---")
        
        # Heuristic to find columns containing table names
        tbl_cols = [c for c in df_map.columns if "tbl" in c.lower() or "table" in c.lower()]
        
        for _, row in df_map.iterrows():
            for t_col in tbl_cols:
                t_name = str(row[t_col]).strip()
                if t_name in tables:
                    # Found a match, capture the full row as mapping description
                    summary.append(f"\nMapping row for {t_name}:")
                    summary.append(row.to_string())
                        
    except Exception as e:
        summary.append(f"Error searching mapping metadata: {e}")
    finally:
        conn.close()
        
    return "\n".join(summary) if len(summary) > 1 else "No mapping metadata found for specified tables."

def get_fsdm_summary_logic(project_name: str, tables: List[str]) -> str:
    """
    Analyzes all 'fsdm_etl_' tables to find metadata matching the provided business table names.
    Returns technical metadata/schema summaries for those specific tables.
    """
    db_uri = ProjectManager.get_db_uri(project_name)
    db = SQLDatabase.from_uri(db_uri)
    conn = sqlite3.connect(ProjectManager.get_db_path(project_name))
    summary = []
    
    try:
        all_tables = db.get_usable_table_names()
        doc_tables = [t for t in all_tables if t.lower().startswith("fsdm_etl_")]
        
        summary.append(f"--- Business Metadata for tables: {', '.join(tables)} ---")
        
        for doc_table in doc_tables:
            df = pd.read_sql_query(f"SELECT * FROM \"{doc_table}\"", conn)
            
            # Heuristic to find columns containing table names
            tbl_cols = [c for c in df.columns if "tbl" in c.lower() or "table" in c.lower()]
            
            for _, row in df.iterrows():
                for t_col in tbl_cols:
                    t_name = str(row[t_col]).strip()
                    if t_name in tables:
                        # Found a match, capture the full row as schema/metadata description
                        summary.append(f"\nMetadata from {doc_table} for {t_name}:")
                        summary.append(row.to_string())
                        
    except Exception as e:
        summary.append(f"Error searching FSDM documentation: {e}")
    finally:
        conn.close()
        
    return "\n".join(summary) if len(summary) > 1 else "No metadata found for specified tables."

# New Tool Definitions
# VS
@tool
def lg_fetch_vector_context_semantic(query: str, project_name: str) -> str:
    """Performs a semantic search on the Semantic knowledge base."""
    print(f"[Tool: Vector Search] Query: {query}, Project: {project_name}")
    res = fetch_vector_context_semantic(query, project_name)
    print(f"[Tool: Vector Search] Returning result snippet: {res[:200]}...")
    return res

@tool
def lg_fetch_vector_context_fsdm(query: str, project_name: str) -> str:
    """Performs a semantic search on the FSDM knowledge base."""
    print(f"[Tool: Vector Search] Query: {query}, Project: {project_name}")
    res = fetch_vector_context_fsdm(query, project_name)
    print(f"[Tool: Vector Search] Returning result snippet: {res[:200]}...")
    return res

# Semantic
@tool
def lg_get_semantic_metadata(table_name: str, project_name: str) -> str:
    """Extracts enriched metadata (definitions, purpose, instructions) for semantic tables."""
    print(f"[Tool: Semantic Metadata] Table: {table_name}, Project: {project_name}")
    res = get_semantic_metadata_logic(table_name, project_name)
    print(f"[Tool: Semantic Metadata] Result: {res[:200]}...")
    return res

# FSDM
@tool
def lg_get_fsdm_metadata(table_name: str, project_name: str) -> str:
    """Extracts technical metadata and schema descriptions for FSDM/ETL tables."""
    print(f"[Tool: FSDM Metadata] Table: {table_name}, Project: {project_name}")
    res = get_fsdm_metadata_logic(table_name, project_name)
    print(f"[Tool: FSDM Metadata] Result: {res[:200]}...")
    return res

# Common
@tool
def lg_list_tables(project_name: str, table_type: str = "all") -> str:
    """Lists tables based on type: 'all', 'semantic', or 'fsdm'."""
    print(f"[Tool: List Tables] Type: {table_type}, Project: {project_name}")
    res = list_tables_logic(project_name, table_type)
    print(f"[Tool: List Tables] Result: {res}")
    return res


@tool
def lg_query_db(sql_query: str, project_name: str) -> str:
    """Executes a SELECT SQL query against the database."""
    print(f"[Tool: SQL Query] Query: {sql_query}, Project: {project_name}")
    res = query_db_logic(sql_query, project_name)
    print(f"[Tool: SQL Query] Result: {res}...")
    return res

@tool
def lg_get_table_schema(table_name: str, project_name: str) -> str:
    """Returns the CREATE TABLE statement for a specific table."""
    print(f"[Tool: Schema] Table: {table_name}, Project: {project_name}")
    res = get_table_schema_logic(table_name, project_name)
    print(f"[Tool: Schema] Result: {res}")
    return res

@tool
def lg_sample_table_data(table_name: str, project_name: str, n: int = 5) -> str:
    """Returns the first N rows of a table."""
    print(f"[Tool: Sample Data] Table: {table_name}, N: {n}, Project: {project_name}")
    res = sample_table_data_logic(table_name, project_name, n)
    print(f"[Tool: Sample Data] Result: {res}...")
    return res

@tool
def lg_get_instructions(scope: str, project_name: str) -> str:
    """Retrieves instructions for a given scope (global, mapping, fsdm)."""
    print(f"[Tool: Instructions] Fetching scope: {scope}, Project: {project_name}")
    instr = ProjectManager.get_instructions(project_name, scope)
    res = instr if instr and instr.strip() != "" else f"No instructions defined for {scope}."
    print(f"[Tool: Instructions] Result length: {len(res)}")
    return res

# Unused
@tool
def lg_list_fsdm_tables_logic(project_name: str) -> str:
    """Lists available tables in the project's SQLite database that start with 'fsdm_etl_'."""
    print(f"[Tool: List FSDM Tables] Project: {project_name}")
    res = list_fsdm_tables_logic(project_name)
    print(f"[Tool: List FSDM Tables] Result: {res}")
    return res

@tool
def lg_get_mapping_summary(tables: List[str], project_name: str) -> str:
    """Summarizes mapping logic for the provided tables."""
    print(f"[Tool: Mapping Summary] Tables: {tables}, Project: {project_name}")
    res = get_mapping_summary_logic(project_name, tables)
    print(f"[Tool: Mapping Summary] Returning result snippet: {res}...")
    return res

@tool
def lg_get_fsdm_summary(tables: List[str], project_name: str) -> str:
    """Summarizes FSDM logic for the provided tables."""
    print(f"[Tool: FSDM Summary] Tables: {tables}, Project: {project_name}")
    res = get_fsdm_summary_logic(project_name, tables)
    print(f"[Tool: FSDM Summary] Returning result snippet: {res}...")
    return res

# # # @tool
# def get_business_schema_summary(project_name: str) -> str:
#     """
#     Analyzes the mapping metadata and FSDM tables to extract a structured summary 
#     of the actual business tables and columns mentioned in the rows.
#     Returns a format like:
#     Table Name:
#      - Column 1
#      - Column 2
#     """
#     db_uri = ProjectManager.get_db_uri(project_name)
#     db = SQLDatabase.from_uri(db_uri)
    
#     summary = []
    
#     # 1. Analyze mapping_sheet
#     try:
#         df_map = pd.read_sql_query("SELECT * FROM mapping_sheet", sqlite3.connect(ProjectManager.get_db_path(project_name)))
#         if not df_map.empty:
#             summary.append("--- Business Entities from Mapping Sheet ---")
#             # Heuristically find source/target table and column columns
#             # We'll look for keywords in column names
#             tbl_cols = [c for c in df_map.columns if "tbl" in c.lower() or "table" in c.lower()]
#             col_cols = [c for c in df_map.columns if "col" in c.lower() or "field" in c.lower()]
            
#             entities = {}
#             for _, row in df_map.iterrows():
#                 for t_col in tbl_cols:
#                     t_name = str(row[t_col]).strip()
#                     if not t_name or t_name.lower() == "nan" or t_name.lower() == "none": continue
#                     if t_name not in entities: entities[t_name] = set()
#                     for c_col in col_cols:
#                         c_name = str(row[c_col]).strip()
#                         if not c_name or c_name.lower() == "nan" or c_name.lower() == "none": continue
#                         entities[t_name].add(c_name)
            
#             for t, cols in entities.items():
#                 summary.append(f"\nTable: {t}")
#                 for c in sorted(list(cols)):
#                     summary.append(f" - {c}")
#     except Exception as e:
#         summary.append(f"Error mapping sheet: {str(e)}")

#     # 2. Analyze FSDM tables
#     try:
#         tables = db.get_usable_table_names()
#         fsdm_tables = [t for t in tables if "fsdm" in t.lower() or "etl" in t.lower()]
#         if fsdm_tables:
#             summary.append("\n--- Business Entities from FSDM/ETL Documentation ---")
#             for ft in fsdm_tables:
#                 df_fsdm = pd.read_sql_query(f"SELECT * FROM {ft}", sqlite3.connect(ProjectManager.get_db_path(project_name)))
#                 # Similar heuristic
#                 tbl_cols = [c for c in df_fsdm.columns if "tbl" in c.lower() or "table" in c.lower()]
#                 col_cols = [c for c in df_fsdm.columns if "col" in c.lower() or "field" in c.lower()]
                
#                 entities = {}
#                 for _, row in df_fsdm.iterrows():
#                     for t_col in tbl_cols:
#                         t_name = str(row[t_col]).strip()
#                         if not t_name or t_name.lower() == "nan" or t_name.lower() == "none": continue
#                         if t_name not in entities: entities[t_name] = set()
#                         for c_col in col_cols:
#                             c_name = str(row[c_col]).strip()
#                             if not c_name or c_name.lower() == "nan" or c_name.lower() == "none": continue
#                             entities[t_name].add(c_name)
                
#                 for t, cols in entities.items():
#                     summary.append(f"\nTable: {t}")
#                     for c in sorted(list(cols)):
#                         summary.append(f" - {c}")
#     except Exception as e:
#         summary.append(f"Error FSDM: {str(e)}")
        
#     if not summary:
#         return "No business entities could be extracted from metadata."
        
#     return "\n".join(summary)
