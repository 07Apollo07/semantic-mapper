from agent.tools.tools import *                                                                                                                                                                                                                   
# print(fetch_vector_context("Hi","New3")) - passed                                                                   
# print(list_project_tables("New3")) #- passsed                                                                       
# print(get_table_schema("final_mappings", "New3")) - passsed                                                        
# print(sample_table_data("fsdm_etl_sheet1", "New3"))                                                                 
# print(get_business_schema_summary( "New3")) 

project = "New3"
test_table = "fsdm_etl_sheet1"
tables_list = ["TB3", "TB6"]

print("--- Testing Logic Functions ---")
# try:
print("List Tables:", list_project_tables_logic(project))
print("Vector Context (Hi):", fetch_vector_context_logic("Hi", project))
print("Query DB (SELECT name FROM sqlite_master):", query_db_logic("SELECT name FROM sqlite_master", project))
print("Table Schema:", get_table_schema_logic(test_table, project))
print("Sample Data:", sample_table_data_logic(test_table, project))
print("Mapping Summary:", get_mapping_summary_logic(project, tables_list))
print("FSDM Summary:", get_fsdm_summary_logic(project, tables_list))
# except Exception as e:
#     print(f"Error during test execution: {e}")

