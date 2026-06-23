from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, END
from agent.agents.agents_utils import MappingState, MappingOutput
from agent.tools.tools import lg_get_instructions, query_full_db_data
    


def make_general_instructions(project):
    return lg_get_instructions.invoke({"scope": "global", "project_name": project})

def get_from_clause(row_data, project):
    """Generate a simple FROM-clause snippet for the target table.
    """
    # Extract the target table name from the row metadata. Fallback to an empty
    # string so the function never raises if the key is missing.
    table_name = row_data.get('target_info', {}).get('table_name', '')
    if not table_name:
        return ""

    # Fetch a sample row (or the full table definition) using the shared helper.
    # The result of ``query_full_db_data`` is a raw string containing headers and rows.
    # We embed that directly in a nicely formatted multi‑line string so it can be
    # inserted into the LLM prompt.
    sample_data = query_full_db_data(f'''SELECT remarks FROM mapping_semantic_smx_for_d_account_xlsx_sheet1 LIMIT 1''', project)
    return f"""
# FROM Clause for table (Use this from clause)`
{sample_data}
"""

def final_output_instruction():
    return """
You must give a detailed output in reasoning when you output as follows:

---
### 1. lineage_intent
This field MUST contain a complete Discovery Report with detailed explanation.
Format it exactly like this:

## Discovery Report
**1. Source Identification:**
- Primary Source Table: [Table Name]
- Primary Source Column: [Column Name]
- Secondary/Lookup Sources: [Any other tables/columns involved]

**2. Lineage Chain:**
- [Step-by-step path from Target back to Source]

**3. Mapping Considerations:**
- [Any transformation logic found in the docs]
- [Special filtering rules or constants]
- [Business rules mentioned in instructions or metadata]

**4. User-Defined Pattern Report:**
- [List each pattern specified in the FSDM Instructions]
- [Result of the query for that pattern - what was found or "No matches found"]

**5. Verification Status:**
- [Confirmed/Incomplete/Ambiguous - explain why]

---
### 2. findings
- Provide a short 1-3 line summary of what was discovered
- Focus on what the source is and what was mapped

---
### 3. reasoning (STEP LOGIC)
- Step-by-step explanation of how you:
  - Queried metadata
  - Applied patterns
  - Filtered candidates
  - Reached final mapping

---
### 4. recommended_sources
- List ONLY final validated:
  - Source tables
  - Source columns
- No intermediate or exploratory values

For transformation_logic
Only give a complete multiline sql statement which should runm it should have a select statement and only relevant columns which are used for source to target mapping
Output should be short
"""
def create_mapping_custom(model_name="gpt-4o", api_key=None, base_url=None, log_callback=None):
    
    def _log(msg):
        if log_callback:
            log_callback(msg)
        print(msg)

    llm = ChatOpenAI(
        model=model_name,
        # temperature=0,
        api_key=api_key if api_key and api_key.strip() != "" else "not-needed",
        base_url=f"{base_url.rstrip('/')}/v1" if base_url else None
    )

    structured_llm = llm.with_structured_output(MappingOutput)

    def init_node(state: MappingState):
        project = state['project_name']
        row_data = state['row_data']
        s_info = row_data.get('source_info', {})
        t_info = row_data.get('target_info', {})
        ps_info = row_data.get('physical_source_info', {})
        trans_specs = row_data.get('transformation_specs', {})
        # Fetch contextual instructions
        global_instr = lg_get_instructions.invoke({"scope": "global", "project_name": project})
        mapping_instr = lg_get_instructions.invoke({"scope": "mapping", "project_name": project})

        system_prompt = """
You are an expert SQL Mapping Architect.
1. The Semantic Target (A) is produced by joining FSDM tables (B).
2. The B tables are filtered/constrained by conditions found in the Physical Source ETL tables (C).
3. Physical source fields (C) provide additional context and may be used for filtering or column selection.
Goal: Generate a correct SQL mapping based on the provided target, source, transformation rules, and FSDM technical definitions, including the physical source information.

Logic:
- Generate a complete multiline SELECT statement.
- For 1:1, Mappings as well as Joins, Make sure to understand What the column means and what values whould go in it, and choose the appropriate Soure Column from C
- identify whats the ost appropriate Source (C) and give that in your reasoning, What were considered, what were eliminated and what was chosen
- Use WHERE clauses to apply conditions derived from Source ETL tables (C) to the A-layer.
- Pay close attention to the definitions and column source mappings provided in the context.
- Pay close attention to Mapping instructions, for where clause its not necessary to use the same source, it could come in from other columns as well
For the where clause we use all available columns from B, not just target column, so pay close attention to them as well, we join using target columns but for filtering and where clause it can be any column from the tables of B
and if transformation type is a join it shoulld contain a where clause in the transformation logic
"""

        user_content = f"""
#FSDM (B) to Semantic (A)
Semantic Target (A): {t_info}
Accompanying FSDM Schema (B): {s_info}
Physical Source Information (C): {ps_info}
Transformation specs between : {trans_specs}

<instructions>
- **Global Style/Patterns:** {global_instr}
- **Mapping-Specific Rules:** {mapping_instr}
</instructions>

### 1. Core Mapping Requirements (Primary Source for SELECT)
The following information defines the base mapping logic:

**Source Information:**
- **Subject Area:** {s_info.get('subject_area', 'N/A')}
- **Database:** {s_info.get('db_name', 'N/A')}
- **Table:** {s_info.get('table_name', 'N/A')}
- **Column:** {s_info.get('column_name', 'N/A')}
- **Datatype:** {s_info.get('datatype', 'N/A')}

**Target Information:**
- **Subject Area:** {t_info.get('subject_area', 'N/A')}
- **Database:** {t_info.get('db_name', 'N/A')}
- **Entity Name (Just for reference):** {t_info.get('table_name', 'N/A')}
- **Column:** {t_info.get('column_name', 'N/A')}
- **Datatype:** {t_info.get('datatype', 'N/A')}

**Physical Source Information:**
- **Subject Area:** {ps_info.get('subject_area', 'N/A')}
- **Database:** {ps_info.get('db_name', 'N/A')}
- **Table:** {ps_info.get('table_name', 'N/A')}
- **Column:** {ps_info.get('column_name', 'N/A')}
- **Datatype:** {ps_info.get('datatype', 'N/A')}

**Transformation Specifications:**
- **Type:** {trans_specs.get('type', 'N/A')}
- **Condition:** {trans_specs.get('condition', 'N/A')}
- **Remarks:** {trans_specs.get('remarks', 'N/A')}

**From Clause (Use this from clause):**
{get_from_clause(row_data, project)}

If there are multiple source tables and source columns, find which columb belongs to which table
{final_output_instruction()}
Keep the final response short and concise
"""
        
        return {"messages": [SystemMessage(content=system_prompt), HumanMessage(content=user_content)]}

    def generate_node(state: MappingState):
        messages = state['messages']
        
        # Debugging sanity prints
        print(f"\n--- [Custom Mapping: System Prompt] ---")
        messages[0].pretty_print()
        print(f"\n--- [Custom Mapping: User Content] ---")
        messages[1].pretty_print()
        
        response = structured_llm.invoke(messages)
        
        tool_call_id = "call_" + str(hash(response.transformation_logic))[-10:]
        ai_message = AIMessage(
            content="",
            tool_calls=[{
                "name": "MappingOutput",
                "args": {
                    "transformation_type": response.transformation_type,
                    "transformation_logic": response.transformation_logic,
                    "reasoning": response.reasoning
                },
                "id": tool_call_id
            }]
        )
        
        return {
            "transformation_type": response.transformation_type,
            "transformation_logic": response.transformation_logic,
            "reasoning": response.reasoning,
            "messages": [ai_message]
        }

    workflow = StateGraph(MappingState)
    workflow.add_node("init", init_node)
    workflow.add_node("generate", generate_node)
    
    workflow.set_entry_point("init")
    workflow.add_edge("init", "generate")
    workflow.add_edge("generate", END)
    
    return workflow.compile()
