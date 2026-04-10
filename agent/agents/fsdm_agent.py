from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from .agents_utils import FSDMDiscoveryState, FSDMIntentOutput
from agent.tools import search_documentation, get_table_schema

def create_fsdm_discovery_agent(model_name="gpt-4o", api_key=None, base_url=None, log_callback=None):
    llm = ChatOpenAI(
        model=model_name,
        temperature=0.1,
        api_key=api_key if api_key and api_key.strip() != "" else "not-needed",
        base_url=f"{base_url.rstrip('/')}/v1" if base_url else None
    )
    llm_with_tools = llm.bind_tools([FSDMIntentOutput])

    def invoke(state: FSDMDiscoveryState):
        if log_callback: log_callback(f"🚀 [FSDM Agent] Discovering lineage for: {state['source_info'].get('table_name')}")
        
        # 1. Fetch FSDM/ETL Documentation
        s_tbl = state['source_info'].get('table_name')
        fsdm_context = search_documentation.invoke({
            "query_term": s_tbl, 
            "project_name": state['project_name']
        }) if s_tbl else "No source table provided."
        
        # 2. Fetch Schema
        schema = get_table_schema.invoke({
            "table_name": s_tbl, 
            "project_name": state['project_name']
        }) if s_tbl else ""

        system_prompt = f"""You are an FSDM Discovery Agent.
Your goal is to explain how raw FSDM source columns are derived from ETL processes.

<fsdm_metadata>
{fsdm_context}
</fsdm_metadata>

<technical_schema>
{schema}
</technical_schema>

<fsdm_instructions>
{state.get('fsdm_instructions', 'None')}
</fsdm_instructions>

YOU MUST FINISH BY CALLING THE `FSDMIntentOutput` TOOL.
"""
        
        user_prompt = f"""
Analyze the FSDM lineage for the following column:
Source Table: {state['source_info'].get('table_name')}
Source Column: {state['source_info'].get('column_name')}

Provide the lineage intent using the FSDMIntentOutput tool.
"""
        
        response = llm_with_tools.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
        
        # Extract Output
        lineage = ""
        status = "Requires_Verification"
        if hasattr(response, 'tool_calls') and response.tool_calls:
            for tc in response.tool_calls:
                if tc['name'] == 'FSDMIntentOutput':
                    lineage = tc['args'].get('lineage_intent', '')
                    status = tc['args'].get('status', 'Identified')
        
        if log_callback: log_callback(f"✅ [FSDM Agent] Discovery complete. Status: {status}")
        return {"fsdm_lineage_intent": lineage, "fsdm_status": status}

    class FSDMAgent:
        def invoke(self, state: FSDMDiscoveryState):
            return invoke(state)
            
    return FSDMAgent()
