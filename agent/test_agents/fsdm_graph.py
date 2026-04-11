from typing import TypedDict, List, Dict, Any, Optional, Annotated
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END, MessageGraph
from langgraph.prebuilt import ToolNode
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from agent.agents.agents_utils import FSDMDiscoveryState, FSDMIntentOutput
from agent.tools.tools import (
    lg_fetch_vector_context,
    lg_get_fsdm_summary,
    lg_get_instructions,
    lg_get_table_schema,
    lg_query_db
)

def should_continue(state: FSDMDiscoveryState):
    last_message = state['messages'][-1]
    if last_message.tool_calls:
        for tc in last_message.tool_calls:
            if tc['name'] == 'FSDMIntentOutput':
                return "end"
        return "tools"
    return "end"

def create_fsdm_graph(model_name="gpt-4o", api_key=None, base_url=None):
    llm = ChatOpenAI(
        model=model_name,
        temperature=0.1,
        api_key=api_key if api_key and api_key.strip() != "" else "not-needed",
        base_url=f"{base_url.rstrip('/')}/v1" if base_url else None
    )
    
    # Define available tools
    tools = [lg_get_table_schema, lg_query_db]
    tool_node = ToolNode(tools)
    model = llm.bind_tools(tools + [FSDMIntentOutput])

    workflow = StateGraph(FSDMDiscoveryState)

    def agent_node(state: FSDMDiscoveryState):
        project = state['project_name']
        source_info = state['source_info']
        source_table = source_info.get('table_name')
        source_col = source_info.get('column_name')
        
        # 1. Fetch contextual metadata upfront
        vector_context = lg_fetch_vector_context.invoke({"query": f"lineage for {source_table}", "project_name": project})
        fsdm_summary = lg_get_fsdm_summary.invoke({"tables": [source_table], "project_name": project})
        global_instr = lg_get_instructions.invoke({"scope": "global", "project_name": project})
        fsdm_instr = lg_get_instructions.invoke({"scope": "fsdm", "project_name": project})
        
        # 2. Build system prompt with gathered context
        system_prompt = f"""You are an expert FSDM Discovery Agent.
Your goal is to identify the lineage of raw FSDM source columns and explain their derivation from ETL processes.

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

Target Column for Analysis: {source_table}.{source_info.get('column_name')}

Process flow:
1. SCHEMA DISCOVERY: Use `get_table_schema` on available FSDM tables to find which ones contain the relevant column.
2. CONTEXT GATHERING: Use `search_documentation` to understand business rules for the identified tables.
3. LINEAGE TRACING: Trace the path backwards (e.g., Target Mapping Table <- Source Table B <- Ultimate Source Table C).
4. SYNTHESIS: Output the structured findings.

Strategy:
1. Use `lg_get_table_schema` and `lg_query_db` to investigate the technical lineage of the columns.
2. Synthesize findings from metadata and your tool investigations.
3. YOU MUST CALL `FSDMIntentOutput` to provide your final lineage analysis.
"""
        messages = [SystemMessage(content=system_prompt)] + state['messages']
        print(f"[DEBUG] Agent reasoning for: {source_table}.{source_col}")
        response = model.invoke(messages)
        if response.tool_calls:
            print(f"[DEBUG] Agent calling tools: {[tc['name'] for tc in response.tool_calls]}")
        else:
            print(response)
        return {"messages": [response]}

    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)

    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
    workflow.add_edge("tools", "agent")

    return workflow.compile()
