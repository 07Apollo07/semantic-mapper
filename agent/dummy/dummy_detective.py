import json
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from agent.agents.agents_utils import FSDMDiscoveryState, FSDMIntentOutput

def should_continue(state: FSDMDiscoveryState):
    last_message = state['messages'][-1]
    if last_message.tool_calls:
        for tc in last_message.tool_calls:
            if tc['name'] == 'FSDMIntentOutput':
                return "end"
    return "end"

def create_dummy_detective(model_name="gpt-4o", api_key=None, base_url=None):
    workflow = StateGraph(FSDMDiscoveryState)

    def dummy_detective_node(state: FSDMDiscoveryState):
        # Capture all non-message fields for inspection
        input_capture = {k: v for k, v in state.items() if k != "messages"}
        
        # Create a tool call to FSDMIntentOutput populated with input state
        tool_call = {
            "name": "FSDMIntentOutput",
            "args": {
                "lineage_intent": f"INPUT_CAPTURE: {json.dumps(input_capture, indent=2)}",
                "findings": f"SOURCE: {json.dumps(state.get('source_info', {}))}",
                "reasoning": f"PROJECT: {state.get('project_name', 'N/A')}",
                "recommended_sources": [state.get('source_info', {}).get('table_name', 'unknown')]
            },
            "id": "dummy_detective_call",
            "type": "tool_call"
        }
        
        response = AIMessage(content="[DUMMY DETECTIVE] Echoing inputs...", tool_calls=[tool_call])
        return {"messages": [response]}

    workflow.add_node("detective", dummy_detective_node)
    workflow.set_entry_point("detective")
    workflow.add_conditional_edges("detective", should_continue, {"end": END})

    return workflow.compile()
