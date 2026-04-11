from agent.tools.tools import (
    lg_fetch_vector_context,
    lg_get_fsdm_summary,
    lg_get_instructions
)

def test_fsdm_discovery_prompt(project_name="New3", business_tables=["TB3", "TB6"]):
    print(f"--- Testing FSDM Discovery Prompt Construction for: {business_tables} ---")
    
    # 1. Fetch Vector Store context (lineage search)
    vector_context = lg_fetch_vector_context.invoke({
        "query": f"lineage discovery for tables {business_tables}", 
        "project_name": project_name
    })
    
    # 2. Fetch FSDM Summary (technical metadata)
    fsdm_summary = lg_get_fsdm_summary.invoke({"tables": business_tables, "project_name": project_name})
    
    # 3. Fetch Instructions (Global + FSDM)
    global_instr = lg_get_instructions.invoke({"scope": "global", "project_name": project_name})
    fsdm_instr = lg_get_instructions.invoke({"scope": "fsdm", "project_name": project_name})
    
    # 4. Construct FSDM Discovery System Prompt
    system_prompt = f"""You are an FSDM Discovery Agent.
Your goal is to identify the lineage of the raw FSDM source columns and explain how they are derived from ETL processes.

<vector_store_context>
{vector_context}
</vector_store_context>

<fsdm_metadata>
{fsdm_summary}
</fsdm_metadata>

<instructions>
[Global]: {global_instr}
[FSDM]: {fsdm_instr}
</instructions>

Analyze the FSDM lineage and explain how the specified business columns in {business_tables} are derived.
"""
    
    print("\n--- Final FSDM Discovery System Prompt ---")
    print(system_prompt)
    print("------------------------------------------")

if __name__ == "__main__":
    test_fsdm_discovery_prompt()
