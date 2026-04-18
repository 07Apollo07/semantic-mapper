# Proposed Tools Registry

This document outlines the proposed organization for agent tools to improve discoverability and agent performance. Tools are categorized by domain, ensuring agents can selectively load or prioritize information based on their current task.

---

## 1. Vector Store
*   **`lg_fetch_vector_context(query: str, project_name: str)`**
    *   **Description**: Performs semantic search on the project knowledge base (PDFs/Docs).
    *   **Agent Utility**: Use this to retrieve unstructured business context, definitions, or broad documentation that isn't stored in a structured database format.

## 2. Semantic (Metadata/Intelligence)
*   **`lg_get_semantic_metadata(table_name: str, project_name: str)`**
    *   **Description**: Extracts enriched metadata (definitions, purpose, instructions) associated with semantic tables.
    *   **Agent Utility**: Provides the "what" and "why" behind business-level entities defined in the Semantic Knowledge Base.
*   **`lg_list_tables(type="semantic")`**
    *   **Description**: Lists only the tables prefixed with `semantic_`.
    *   **Agent Utility**: Constrains the agent's view to business-domain tables.

## 3. FSDM (Discovery/Documentation)
*   **`lg_get_fsdm_metadata(table_name: str, project_name: str)`**
    *   **Description**: Extracts technical metadata and schema descriptions from FSDM/ETL documentation tables.
    *   **Agent Utility**: Provides the "how" (technical implementation details) for FSDM/ETL structures.
*   **`lg_list_tables(type="fsdm")`**
    *   **Description**: Lists only the tables prefixed with `fsdm_etl_`.
    *   **Agent Utility**: Constrains the agent's view to technical ETL/Data Model tables.

## 4. Final Mappings
*   **`lg_get_mapping_summary(tables: List[str], project_name: str)`**
    *   **Description**: Analyzes the `mapping_sheet` to provide curated mapping metadata for specific tables.
    *   **Agent Utility**: The primary source for understanding established technical mapping links between source and target systems.

## 5. Common (Foundation)
*   **`lg_list_tables(type="all")`**
    *   **Description**: Lists all tables currently in the project database.
*   **`lg_query_db(sql_query: str, project_name: str)`**
    *   **Description**: Executes `SELECT` queries against the project database.
    *   **Agent Utility**: The "Golden Tool". Use this for raw data retrieval when higher-level summaries or metadata tools aren't sufficient.
*   **`lg_get_instructions(scope: str, project_name: str)`**
    *   **Description**: Fetches user-provided system instructions for a given scope (global, mapping, fsdm).
*   **`lg_get_table_schema(table_name: str, project_name: str)`**
    *   **Description**: Retrieves the raw `CREATE TABLE` definition.
*   **`lg_sample_table_data(table_name: str, project_name: str, n=5)`**
    *   **Description**: Fetches the first N rows from a table.
