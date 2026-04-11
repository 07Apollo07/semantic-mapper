import json
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from agent.agents.agents_utils import SemanticMappingState, MappingOutput

def should_continue(state: SemanticMappingState):
    last_message = state['messages'][-1]
    if last_message.tool_calls:
        for tc in last_message.tool_calls:
            if tc['name'] == 'MappingOutput':
                return "end"
    return "end"

def create_dummy_engineer(model_name="gpt-4o", api_key=None, base_url=None):
    workflow = StateGraph(SemanticMappingState)

    def dummy_engineer_node(state: SemanticMappingState):
        # Capture all non-message fields for inspection
        input_capture = {k: v for k, v in state.items() if k != "messages"}
        
        # Create a tool call to MappingOutput populated with input state
        tool_call = {
            "name": "MappingOutput",
            "args": {
                "transformation_type": "DUMMY_ECHO",
                "transformation_logic": f"INPUT_CAPTURE: {json.dumps(input_capture, indent=2)}",
                "reasoning": f"SOURCE: {json.dumps(state.get('source_info', {}))} | TARGET: {json.dumps(state.get('target_info', {}))}"
            },
            "id": "dummy_engineer_call",
            "type": "tool_call"
        }
        
        response = AIMessage(content="[DUMMY ENGINEER] Echoing inputs...", tool_calls=[tool_call])
        return {"messages": [response]}

    workflow.add_node("engineer", dummy_engineer_node)
    workflow.set_entry_point("engineer")
    workflow.add_conditional_edges("engineer", should_continue, {"end": END})

    return workflow.compile()
