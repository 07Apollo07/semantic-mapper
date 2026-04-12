from typing import TypedDict, List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from agent.agents.agents_utils import FSDMDiscoveryState, FSDMIntentOutput
from agent.tools.tools import (
    lg_get_instructions,
    lg_get_table_schema,
    lg_query_db,
    lg_list_fsdm_tables_logic
)

def should_continue(state: FSDMDiscoveryState):
    last_message = state['messages'][-1]
    if last_message.tool_calls:
        print(f"[Detective Debug] Tool calls detected: {[tc['name'] for tc in last_message.tool_calls]}")
        for tc in last_message.tool_calls:
            if tc['name'] == 'FSDMIntentOutput':
                print(f"[Detective Debug] FSDMIntentOutput called. Ending.")
                return "end"
        return "tools"
    print(f"[Detective Debug] No tool calls. Ending.")
    return "end"

def create_fsdm_detective(model_name="gpt-4o", api_key=None, base_url=None):
    llm = ChatOpenAI(
        model=model_name,
        temperature=0.1,
        api_key=api_key if api_key and api_key.strip() != "" else "not-needed",
        base_url=f"{base_url.rstrip('/')}/v1" if base_url else None
    )
    
    # Discovery tools
    tools = [lg_get_table_schema, lg_query_db, lg_list_fsdm_tables_logic]
    tool_node = ToolNode(tools)
    model = llm.bind_tools(tools + [FSDMIntentOutput])

    workflow = StateGraph(FSDMDiscoveryState)

    def detective_node(state: FSDMDiscoveryState):
        project = state['project_name']
        source_info = state['source_info']
        target_table = source_info.get('table_name')
        target_col = source_info.get('column_name')
        feedback = state.get('feedback')

        print(f"[Detective Debug] Current History: {state['messages']}")
        print(f"[Detective Debug] Processing {target_table}.{target_col} for project {project}")

        # 1. Fetch instructional context
        global_instr = lg_get_instructions.invoke({"scope": "global", "project_name": project})
        fsdm_instr = lg_get_instructions.invoke({"scope": "fsdm", "project_name": project})

        # 2. Get list of available mapping tables
        mapping_tables = lg_list_fsdm_tables_logic.invoke({"project_name": project})

        feedback_section = f"\n<human_feedback>\n{feedback}\n</human_feedback>\n" if feedback else ""

        system_prompt = f"""### Role
    You are an expert **FSDM Lineage Detective**. Your task is to trace the lineage of a target column from a target table to its source column in an ETL process.

    ### Project Name: {project}

    ## Available ETL Mapping Documentation Tables:
    {mapping_tables}

    ### Goal: Trace Lineage (Target -> Source)
    - **Target Table:** `{target_table}`
    - **Target Column:** `{target_col}`

    ### How the Data is Structured:
    The ETL mapping is stored in SQLite tables (prefixed with `fsdm_etl_`).
    Each table has rows structured like: `[TargetTable, TargetColumn, SourceColumn, SourceTable]`.
    Example: `TB1, C1, S1, TS1` means `C1` in `TB1` is derived from `S1` in `TS1`.

    ### Contextual Data
    <fsdm_table_metadata>
    {state.get('metadata', 'No table metadata provided.')}
    </fsdm_table_metadata>

    <instructions>
    - **Global Styles:** {global_instr}
    - **FSDM-Specific Rules:** {fsdm_instr}
    </instructions>
    {feedback_section}

    ### Your Process:
    1. **Examine Schema:** Use `lg_get_table_schema` to identify `TargetTable`, `TargetColumn`, `SourceTable`, and `SourceColumn` columns.
    2. **Query Lineage:** Use `lg_query_db` to run a SELECT query.
    3. **Synthesize:** Call `FSDMIntentOutput` with your findings.

    ### Response Constraints
    - **Format:** Single, concise paragraph with bullet points.
    - **Content:** State the lineage hierarchy.
    - **Requirement:** **YOU MUST CALL `FSDMIntentOutput` to finish your task.**

    When using the query tool, remember u are querying a sqlite db, so format prompt accordingly.
    If after multiple attempts u cant find the output or some definitive answer, return back your findings do not go in a infinite loop.
    """
        messages = state['messages']
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=system_prompt)] + messages
        else:
            messages[0] = SystemMessage(content=system_prompt)

        response = model.invoke(messages)

        return {"messages": [response]}



    workflow.add_node("detective", detective_node)
    workflow.add_node("tools", tool_node)
    workflow.set_entry_point("detective")
    workflow.add_conditional_edges("detective", should_continue, {"tools": "tools", "end": END})
    workflow.add_edge("tools", "detective")

    return workflow.compile()
