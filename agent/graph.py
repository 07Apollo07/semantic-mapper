from typing import TypedDict, List, Dict, Any, Literal, Union
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
from .tools import get_tools

load_dotenv()

# Define the structured output model
class TransformationOutput(BaseModel):
    transformation_type: str = Field(description="Type of transformation: e.g., 1:1 mapping, rename, Left-Join, Right join, Outer Join, Inner Join, aggregation etc.")
    transformation_logic: str = Field(description="The complete single-line SQL transforming source column(s) to the target semantic column.")
    reasoning: str = Field(description="Short explanation why this transformation is needed, citing evidence from context.")

# Define the state for the graph
class AgentState(TypedDict):
    source_info: Dict[str, Any]
    target_info: Dict[str, Any]
    transformation_specs: Dict[str, Any]
    context: str
    project_name: str
    messages: List[BaseMessage]
    transformation_type: str
    transformation_logic: str
    reasoning: str
    feedback: str

def create_agent(retriever, model_name="gpt-4o", api_key=None, base_url=None, log_callback=None, project_name=None):
    """Creates the LangGraph agent with tool support and initial context seeding."""
    
    def _log(msg):
        if log_callback:
            log_callback(msg)
        print(msg)

    # Initialize the LLM
    llm = ChatOpenAI(
        model=model_name,
        temperature=0.2,
        api_key=api_key if api_key and api_key.strip() != "" else "not-needed",
        base_url=f"{base_url.rstrip('/')}/v1" if base_url else None
    )

    # Get project-specific tools
    tools = get_tools(project_name)
    # Bind tools and the structured output tool
    llm_with_tools = llm.bind_tools(tools + [TransformationOutput])

    def init_node(state: AgentState):
        """Initializes context from vector store and sets up the prompt."""
        s = state['source_info']
        t = state['target_info']
        
        # Build initial query for vector store context
        query_parts = []
        def add_parts(prefix, val):
            if not val or val == "N/A": return
            sub_parts = [p.strip() for p in str(val).split(',') if p.strip()]
            for p in sub_parts:
                query_parts.append(f"{prefix}: {p}")

        add_parts("Source Table", s.get('table_name'))
        add_parts("Source Column", s.get('column_name'))
        add_parts("Target Table", t.get('table_name'))
        add_parts("Target Column", t.get('column_name'))
        
        query = " | ".join(query_parts)
        _log(f"🔍 [Initial Retrieval] Query: {query}")
        
        docs = retriever.invoke(query)
        context = "\n\n".join([doc.page_content for doc in docs])
        
        system_prompt = f"""You are an expert SQL generator for semantic mapping.
Your goal is to transform source column(s) into a target semantic column.

TOOLS AVAILABLE:
1. vector_tool: Search unstructured documentation (PDFs, docs) for business rules.
2. fsdm_tool: Query structured FSDM/ETL documentation (SQLite) for schemas and technical details.
3. mapping_tool: Query the primary mapping sheet (SQLite) to check existing patterns.

PROCEDURE:
- Use the tools to gather more information if the initial context is insufficient.
- FSDM/ETL queries are best for finding precise column descriptions or join keys.
- Once you have the logic, you MUST call the 'TransformationOutput' tool to provide your final answer.

GUIDELINES:
- Transformation logic must be a single-line SQL statement.
- Do NOT use WHERE clauses in the mapping logic.
- Cite evidence from your search results in the reasoning.

INITIAL CONTEXT FROM VECTOR STORE:
{context if context else "No initial context found."}
"""

        user_content = f"""
Transform source into target.

SOURCE:
- Table: {s.get('table_name')}
- Column: {s.get('column_name')}
- Datatype: {s.get('datatype')}

TARGET:
- Table: {t.get('table_name')}
- Column: {t.get('column_name')}
- Datatype: {t.get('datatype')}

SPECS:
- Type: {state['transformation_specs'].get('type')}
- Condition: {state['transformation_specs'].get('condition')}
- Remarks: {state['transformation_specs'].get('remarks')}

FEEDBACK/CORRECTION:
{state.get('feedback', 'None')}
"""
        return {
            "context": context,
            "messages": [SystemMessage(content=system_prompt), HumanMessage(content=user_content)]
        }

    def agent_node(state: AgentState):
        """Calls the LLM."""
        _log("🚀 [Agent] Thinking...")
        response = llm_with_tools.invoke(state['messages'])
        return {"messages": [response]}

    def should_continue(state: AgentState):
        """Determines if the agent should call a tool or end."""
        messages = state['messages']
        last_message = messages[-1]
        
        if not last_message.tool_calls:
            return END
        
        # Check if the agent called the final output tool
        for tool_call in last_message.tool_calls:
            if tool_call['name'] == 'TransformationOutput':
                return "process"
        
        return "tools"

    def process_node(state: AgentState):
        """Extracts the final structured output from the tool call."""
        last_message = state['messages'][-1]
        output_call = next(tc for tc in last_message.tool_calls if tc['name'] == 'TransformationOutput')
        args = output_call['args']
        
        _log(f"✨ [Agent] Transformation generated: {args.get('transformation_type')}")
        
        return {
            "transformation_type": args.get('transformation_type'),
            "transformation_logic": args.get('transformation_logic'),
            "reasoning": args.get('reasoning')
        }

    # Build the graph
    workflow = StateGraph(AgentState)
    workflow.add_node("init", init_node)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_node("process", process_node)

    workflow.set_entry_point("init")
    workflow.add_edge("init", "agent")
    
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "process": "process",
            END: END
        }
    )
    
    workflow.add_edge("tools", "agent")
    workflow.add_edge("process", END)

    return workflow.compile()
