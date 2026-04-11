from typing import TypedDict, List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from agent.agents.agents_utils import FSDMDiscoveryState, FSDMIntentOutput
from agent.tools.tools import (
    lg_get_instructions,
    lg_get_table_schema,
    lg_query_db
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
    
    # Discovery tools (Manually query based on provided metadata)
    tools = [lg_get_table_schema, lg_query_db]
    tool_node = ToolNode(tools)
    model = llm.bind_tools(tools + [FSDMIntentOutput])

    workflow = StateGraph(FSDMDiscoveryState)

    def detective_node(state: FSDMDiscoveryState):
        project = state['project_name']
        source_info = state['source_info']
        source_table = source_info.get('table_name')
        source_col = source_info.get('column_name')
        feedback = state.get('feedback')
        
        print(f"[Detective Debug] Processing {source_table}.{source_col} for project {project}")
        
        # 1. Fetch instructional context upfront
        global_instr = lg_get_instructions.invoke({"scope": "global", "project_name": project})
        fsdm_instr = lg_get_instructions.invoke({"scope": "fsdm", "project_name": project})
        
        print(f"[Detective Debug] Fetched global/fsdm instructions.")
        
        feedback_section = f"\n<human_feedback>\n{feedback}\n</human_feedback>\n" if feedback else ""

        # 2. Build system prompt using the human-refined metadata for the table
        system_prompt = f"""### Role
You are an expert **FSDM Lineage Detective**. Your goal is to identify how a specific column is derived from source systems by investigating documentation tables.

### Target Context
- **Source Table:** `{source_table}`
- **Source Column:** `{source_col}`

### Contextual Data
<fsdm_table_metadata>
{state.get('metadata', 'No table metadata provided.')}
</fsdm_table_metadata>

<instructions>
- **Global Styles:** {global_instr}
- **FSDM-Specific Rules:** {fsdm_instr}
</instructions>
{feedback_section}

### Strict Heuristic Rules
1. **Metadata First:** Use the `<fsdm_table_metadata>` to identify which physical columns in the documentation tables contain the lineage information.
2. **Follow Instructions:** Strictly adhere to patterns defined in `<instructions>` (e.g., lookup priority, filter logic, naming conventions).
3. **Verified Discovery:** You MUST use `lg_query_db` to fetch specific rows from the relevant 'fsdm_etl_' documentation tables to confirm the source.

### Process Flow
1. **Schema Discovery:** Use `lg_get_table_schema` to understand the structure of the documentation tables.
2. **Context Gathering:** Analyze the metadata and instructions to identify special logic patterns (lookups, filter tables).
3. **Lineage Tracing:** Perform surgical `SELECT` queries via `lg_query_db` to trace the path backwards from the target column to its source.
4. **Synthesis:** Call `FSDMIntentOutput` to submit your final findings, providing a clear explanation of the lineage chain.

### Execution Strategy
- Start by querying the documentation table associated with `{source_table}`.
- If you find multiple potential sources, apply project rules or provide your best technical hypothesis.
- **YOU MUST CALL `FSDMIntentOutput` to finish your task.**
"""
        messages = [SystemMessage(content=system_prompt)] + state['messages']
        response = model.invoke(messages)
        
        if response.content:
            print(f"[Detective Debug] Model thoughts: {response.content}...")
        
        return {"messages": [response]}

    workflow.add_node("detective", detective_node)
    workflow.add_node("tools", tool_node)

    workflow.set_entry_point("detective")
    workflow.add_conditional_edges("detective", should_continue, {"tools": "tools", "end": END})
    workflow.add_edge("tools", "detective")

    return workflow.compile()
