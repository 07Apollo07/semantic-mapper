from agent.tools.tools import (
    fetch_vector_context_semantic,
    fetch_vector_context_fsdm,
    get_semantic_metadata_logic,
    get_fsdm_metadata_logic,
    list_tables_logic,
    query_db_logic,
    get_table_schema_logic,
    sample_table_data_logic,
    get_mapping_summary_logic,
    get_fsdm_summary_logic
)

project = "Horse"
semantic_table = "semantic_sheet1"
fsdm_table = "fsdm_etl_sheet1"
tables_list = ["semantic_sheet1", "fsdm_etl_sheet1"]

print(f"--- Testing Logic Functions for Project: {project} ---")

try:
    print("1. List All Tables:", list_tables_logic(project, "all"))
    print("2. List Semantic Tables:", list_tables_logic(project, "semantic"))
    print("3. List FSDM Tables:", list_tables_logic(project, "fsdm"))
    
    print("\n4. Semantic Vector Context:", fetch_vector_context_semantic("What is the goal?", project))
    print("5. FSDM Vector Context:", fetch_vector_context_fsdm("What are the columns?", project))
    
    print("\n6. Get Semantic Metadata:", get_semantic_metadata_logic(semantic_table, project))
    print("7. Get FSDM Metadata:", get_fsdm_metadata_logic(fsdm_table, project))
    
    print("\n8. Query DB (SELECT count(*) FROM sqlite_master):", query_db_logic("SELECT count(*) FROM sqlite_master", project))
    
    print("\n9. Table Schema:", get_table_schema_logic(fsdm_table, project))
    print("10. Sample Data:", sample_table_data_logic(fsdm_table, project))
    
    print("\n11. Mapping Summary:", get_mapping_summary_logic(project, tables_list))
    print("12. FSDM Summary:", get_fsdm_summary_logic(project, tables_list))

except Exception as e:
    print(f"\n❌ Error during test execution: {e}")
