from typing import TypedDict, List, Dict, Any, Literal, Union
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.utilities import SQLDatabase
from logic.project_manager import ProjectManager
from dotenv import load_dotenv
from .tools import get_tools

load_dotenv()

# Define the structured output model
class TransformationOutput(BaseModel):
    transformation_type: str = Field(description="Type of transformation: e.g., 1:1 mapping, rename, Left-Join, Right join, Outer Join, Inner Join, aggregation etc.")
    transformation_logic: str = Field(description="The complete single-line SQL transforming source column(s) to the target semantic column.")
    reasoning: str = Field(description="Short explanation why this transformation is needed, citing evidence from context and tools.")

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
    global_instructions: str
    pre_mapping_insight: str

def create_agent(retriever, model_name="gpt-4o", api_key=None, base_url=None, log_callback=None, project_name=None):
    """Creates the LangGraph agent with tool support and initial context seeding."""
    
    if not model_name:
        raise ValueError("model_name must be a non-empty string")

    def _log(msg):
        if log_callback:
            log_callback(msg)
        print(msg)

    # Initialize the LLM
    llm = ChatOpenAI(
        model=model_name,
        temperature=0.1, # Lower temperature for more consistent SQL generation
        api_key=api_key if api_key and api_key.strip() != "" else "not-needed",
        base_url=f"{base_url.rstrip('/')}/v1" if base_url else None
    )

    # Get project-specific tools
    tools = get_tools(project_name, log_callback=log_callback)
    # Bind tools and the structured output tool
    llm_with_tools = llm.bind_tools(tools + [TransformationOutput])

    def init_node(state: AgentState):
        """Initializes context from vector store, fetches SQL schema, and sets up the prompt."""
        s = state['source_info']
        t = state['target_info']
        project_name = state['project_name']
        
        # 1. Build initial query for vector store context (Richer Retrieval Logic)
        query_parts = []
        
        def add_parts(prefix, val):
            if not val or val == "N/A": return
            # Split by comma to handle multiple entries
            sub_parts = [p.strip() for p in str(val).split(',') if p.strip()]
            for p in sub_parts:
                query_parts.append(f"{prefix}: {p}")

        add_parts("Source DB", s.get('db_name'))
        add_parts("Source Table", s.get('table_name'))
        add_parts("Source Column", s.get('column_name'))
        
        add_parts("Target DB", t.get('db_name'))
        add_parts("Target Table", t.get('table_name'))
        add_parts("Target Column", t.get('column_name'))
        
        query = " | ".join(query_parts)
        if not query:
            query = "No specific source/target info provided."

        _log(f"🔍 [Agent: Init] Richer Retrieval Query: {query}")
        
        docs = retriever.invoke(query)
        context = "\n\n".join([doc.page_content for doc in docs])
        
        if context:
            _log(f"✅ [Agent: Init] Found {len(docs)} relevant context snippets.")
        else:
            _log("⚠️ [Agent: Init] No relevant context found.")
        
        # 2. Fetch SQL Schema for all tables
        db_schema = "Unknown"
        try:
            db_uri = ProjectManager.get_db_uri(project_name)
            db = SQLDatabase.from_uri(db_uri)
            db_schema = db.get_table_info()
            _log(f"📋 [Agent: Init] Database schema retrieved.")
        except Exception as e:
            _log(f"⚠️ [Agent: Init] Failed to fetch DB schema: {str(e)}")

        system_prompt_content = f"""You are an expert Data Engineer and SQL Architect specializing in semantic mapping.
Your goal is to transform source column(s) into a target semantic column based on the provided intent and metadata.

STRICT OPERATIONAL RULES:
1. NEVER ask the user for clarification. Use your tools to find missing information.
2. If you don't know a table name, call `list_tables_tool`.
3. If you need column details, query the `fsdm_tool` or `mapping_tool` with SQL.
4. You MUST finish by calling the `TransformationOutput` tool. Plain text responses are not allowed as a final answer.
5. The transformation logic MUST be a single-line SQL expression.
6. Do NOT use WHERE clauses in the mapping logic.

MAPPING GUIDELINES:
1. Decide the appropriate transformation type (rename, 1:1 mapping, join, aggregation, etc.).
2. If multiple source databases or tables are mentioned, they likely require a JOIN.
3. For multiple source columns, determine the relationship (e.g., concatenation, arithmetic, or join keys).
4. Use provided context and Transformation Specs as strong requirements for the logic.
5. If multiple databases are provided (e.g. "accounts, Task"), use them to qualify tables or understand scope.

DATABASE SCHEMA:
{db_schema}

VERIFIED INTENT (YOUR PRIMARY GUIDE):
{state.get('pre_mapping_insight', 'None')}

GLOBAL INSTRUCTIONS:
{state.get('global_instructions', 'None')}

INITIAL CONTEXT FROM VECTOR STORE:
{context if context else "No initial context found."}
"""
        _log(f"📜 [Agent: Init] System Prompt Prepared.")

        user_content = f"""
Transform source column into semantic column.

SOURCE DATA:
- Subject Area: {s.get('subject_area', 'N/A')}
- Database: {s.get('db_name', 'N/A')}
- Table: {s.get('table_name', 'N/A')}
- Column: {s.get('column_name', 'N/A')}
- Datatype: {s.get('datatype', 'N/A')}

TARGET (SEMANTIC) DATA:
- Subject Area: {t.get('subject_area', 'N/A')}
- Database: {t.get('db_name', 'N/A')}
- Table: {t.get('table_name', 'N/A')}
- Column: {t.get('column_name', 'N/A')}
- Datatype: {t.get('datatype', 'N/A')}

TRANSFORMATION SPECS (FROM MAPPING DOCUMENT):
- Provided Type: {state['transformation_specs'].get('type', 'N/A')}
- Provided Condition: {state['transformation_specs'].get('condition', 'N/A')}
- Remarks: {state['transformation_specs'].get('remarks', 'N/A')}

FEEDBACK/CORRECTION:
{state.get('feedback', 'None')}

Begin your analysis and provide the final SQL transformation via TransformationOutput tool.
"""
        _log(f"👤 [Agent: Init] User Prompt Prepared.")
        
        return {
            "context": context,
            "messages": [SystemMessage(content=system_prompt_content), HumanMessage(content=user_content)]
        }

    def agent_node(state: AgentState):
        """Calls the LLM and logs the messages and response."""
        _log(f"--- Agent Node Start ---")
        _log(f"▶️ [Agent: Invoke] Messages Sent: {state['messages']}")
        
        response = llm_with_tools.invoke(state['messages'])
        
        _log(f"◀️ [Agent: Invoke Result] {response}")
        return {"messages": [response]}

    def should_continue(state: AgentState):
        """Determines if the agent should call a tool or end."""
        messages = state['messages']
        if not messages:
            return END # Should not happen if agent_node is called

        last_message = messages[-1]
        
        if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
            # If the agent didn't call a tool, it probably just talked.
            # We need to force it to use TransformationOutput or retry.
            _log("❓ [Agent: Should Continue] No tool calls found. Forcing re-evaluation.")
            return "agent" # Loop back to agent to give it a nudge
        
        # Check if the agent called the final output tool
        for tool_call in last_message.tool_calls:
            if tool_call['name'] == 'TransformationOutput':
                _log("✅ [Agent: Should Continue] TransformationOutput tool called. Proceeding to process.")
                return "process"
        
        # If it called other tools, continue to the tools node
        _log("🛠️ [Agent: Should Continue] Tool call found. Proceeding to tools node.")
        return "tools"

    def process_node(state: AgentState):
        """Extracts the final structured output from the tool call."""
        last_message = state['messages'][-1]
        output_call = next(tc for tc in last_message.tool_calls if tc['name'] == 'TransformationOutput')
        args = output_call['args']
        
        _log(f"✨ [Agent: Process] Final Result Type: {args.get('transformation_type')}")
        
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
            "agent": "agent" # Loop back to agent if it just talked or needs another step
        }
    )
    
    workflow.add_edge("tools", "agent")
    workflow.add_edge("process", END)

    return workflow.compile()
