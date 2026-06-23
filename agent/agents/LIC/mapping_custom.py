from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, END
from agent.agents.agents_utils import MappingState, MappingOutput
from agent.tools.tools import lg_get_instructions, query_full_db_data

def get_semantic_definitions_and_rules(row_data, project):
    def format_table_name(name):
        parts = name.split('_')
        formatted_parts = []
        for part in parts:
            p_lower = part.lower()
            if p_lower == 'dim':
                formatted_parts.append('Dimension')
            elif p_lower == 'fact':
                formatted_parts.append('Fact')
            else:
                formatted_parts.append(part.capitalize())
        return " ".join(formatted_parts)

    semantic_table = row_data.get('target_info', {}).get('table_name', '')
    formatted_table_name = format_table_name(semantic_table)
    semantic_column = row_data.get('target_info', {}).get('column_name', '')

    table_definition = query_full_db_data(f"""SELECT * FROM "semantic_fsdm_table_definitions" WHERE "LIC DM Table Name" = '{formatted_table_name}' """, project)
    column_definition = query_full_db_data(f"""SELECT * FROM "semantic_fsdm_column_definition" WHERE "LIC DM Column Name" = '{semantic_column}' """, project)
    classwork = query_full_db_data(f"""SELECT * FROM "Semantic_fsdm_classword" """, project)
    comments = query_full_db_data(f"""SELECT * FROM "semantic_fsdm_general_comments" """, project)
    
    return f"""
# Definitions for Semantic (A) Table and column names
Table Definition:
{table_definition}

Column Definition:
{column_definition}

Classwork:
{classwork}

General Comments:
{comments}
"""

def get_fsdm_definitions_and_rules(row_data, project):
    source_tables_str = row_data.get('source_info', {}).get('table_name', '')
    source_tables = [t.strip() for t in source_tables_str.split(',')]
    
    table_definitions = []
    column_defs = []
    source_mappings = {} # {(Table, Column): set((SourceTable, SourceColumn))}
    
    for table in source_tables:
        table_def = query_full_db_data(f"""SELECT "Physical Name" as "Table Name","Definition" as "Table Definition" FROM "fsdm_etl_table_definitions" WHERE "Physical Name" = '{table}' """, project)
        table_definitions.append(f"""{table_def}""")
    
        attr_def = query_full_db_data(f"""SELECT * FROM "fsdm_etl_attribute_definitions" WHERE "LIC DM Table Name" = '{table}' """, project)
        column_defs.append(f"""{attr_def}""")
        
        mappings = query_full_db_data(f"""SELECT "LICDM Details_LICDM_TABLE_NAME", "LICDM Details_LICDM_COLUMN_NAME", "Source Details_SOURCE_TABLE_NAME", "Source Details_SOURCE_COLUMN_NAME" FROM "fsdm_etl_columnn_mappings" WHERE "LICDM Details_LICDM_TABLE_NAME" = '{table}' """, project)
        
        if "Rows: [" in mappings:
            rows_str = mappings.split("Rows:")[1].strip()
            try:
                import ast
                rows = ast.literal_eval(rows_str)
                for row in rows:
                    t, c, st, sc = row
                    key = (t, c)
                    if key not in source_mappings:
                        source_mappings[key] = set()
                    source_mappings[key].add((st, sc))
            except Exception:
                pass
    
    common_instr = query_full_db_data(f"""SELECT * FROM "Fsdm_etl_common_mapping_instructions" """, project)
    classwork = query_full_db_data(f"""SELECT * FROM "fsdm_etl_classword" """, project)
    
    formatted_sources = []
    for (t, c), sources in source_mappings.items():
        formatted_sources.append(f"Table: {t}, Column: {c}\nSources: {list(sources)}")
    
    joined_sources = "\n".join(formatted_sources)
    return f"""
# Definitions for FSDM (B) Tables
{table_definitions}

#All FSDM (B) Column Definitions
{column_defs}

# FSDM (B) Column Source Mappings
This section maps each FSDM Table and Column to its unique sources, formatted as a list of (Source Table, Source Column) pairs:
{joined_sources}

# FSDM Common Mapping Instructions
{common_instr}

# FSDM Classwork
{classwork}
"""

def make_fsdm_source_content(row_data):
    return "Source ETL Content (Reserved for detailed sheet-level metadata/filtering logic)."

def make_general_instructions(project):
    return lg_get_instructions.invoke({"scope": "global", "project_name": project})

def final_output_instruction():
    return "Return MappingOutput structured data."

def create_mapping_custom(model_name="gpt-4o", api_key=None, base_url=None, log_callback=None):
    
    def _log(msg):
        if log_callback:
            log_callback(msg)
        print(msg)

    llm = ChatOpenAI(
        model=model_name,
        # temperature=0.7,
        api_key=api_key if api_key and api_key.strip() != "" else "not-needed",
        base_url=f"{base_url.rstrip('/')}/v1" if base_url else None
    )

    structured_llm = llm.with_structured_output(MappingOutput)

    def init_node(state: MappingState):
        project = state['project_name']
        row_data = state['row_data']
        s_info = row_data.get('source_info', {})
        t_info = row_data.get('target_info', {})
        trans_specs = row_data.get('transformation_specs', {})
        
        system_prompt = """
You are an expert SQL Mapping Architect.
1. The Semantic Target (A) is produced by joining FSDM tables (B).
2. The B tables are filtered/constrained by conditions found in the Source ETL tables (C).
Goal: Generate a correct SQL mapping based on the provided target, source, transformation rules, and FSDM technical definitions.

Logic:
- Generate a complete multiline SELECT statement.
- Use JOINs to link the B tables based on the join path whereever necessary.
- Use WHERE clauses to apply conditions derived from Source ETL tables (C) to the B-layer.
- Pay close attention to the definitions and column source mappings provided in the context.
"""

        user_content = f"""
#FSDM (B) to Semantic (A)
Semantic Target (A): {t_info}
Accompanying FSDM Schema (B): {s_info}
Transformation specs between A-B: {trans_specs}

{get_semantic_definitions_and_rules(row_data, project)}
{get_fsdm_definitions_and_rules(row_data, project)}

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
- **Table:** {t_info.get('table_name', 'N/A')}
- **Column:** {t_info.get('column_name', 'N/A')}
- **Datatype:** {t_info.get('datatype', 'N/A')}

**Transformation Specifications:**
- **Type:** {trans_specs.get('type', 'N/A')}
- **Condition:** {trans_specs.get('condition', 'N/A')}
- **Remarks:** {trans_specs.get('remarks', 'N/A')}

Instructions: {make_general_instructions(project)}
{final_output_instruction()}
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
