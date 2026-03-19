from typing import TypedDict, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

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
    transformation_type: str
    transformation_logic: str
    reasoning: str
    feedback: str # Optional feedback for interactive correction

def create_agent(retriever, model_name="gpt-4o", api_key=None, base_url=None, log_callback=None):
    """Creates the LangGraph agent."""
    
    def _log(msg):
        if log_callback:
            log_callback(msg)
        print(msg) # Still print to console for safety

    # Initialize the LLM with custom config
    llm = ChatOpenAI(
        model=model_name,
        temperature=0.2,
        api_key=api_key if api_key and api_key.strip() != "" else "not-needed",
        base_url=f"{base_url.rstrip('/')}/v1" if base_url else None
    )

    # Wrap LLM with structured output
    structured_llm = llm.with_structured_output(TransformationOutput)

    def retrieve_context(state: AgentState):
        """Retrieves relevant context from the vector store."""
        s = state['source_info']
        t = state['target_info']
        
        # Build a richer query including DB and Table names
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

        _log("*" * 40)
        _log(f"🔍 [Retriever] Query: {query}")
        
        docs = retriever.invoke(query)
        context = "\n\n".join([doc.page_content for doc in docs])
        
        if context:
            _log(f"✅ [Retriever] Found {len(docs)} relevant context snippets.")
            _log(f"📄 [Retriever] Context preview: {context[:200]}...")
        else:
            _log("⚠️ [Retriever] No relevant context found.")
            
        return {"context": context}

    def generate_transformation(state: AgentState):
        """Generates the transformation logic based on context and input."""
        _log(f"🚀 [LLM] Generating SQL transformation for {state['source_info'].get('column_name')} -> {state['target_info'].get('column_name')}...")
        
        system_prompt = """You are an expert SQL generator. Your job is to analyze source and target mappings and provide the transformation logic.
        Return a single-line SQL statement that transforms the source column(s) to the target semantic column.
        
        Important Guidelines:
        1. Decide the appropriate transformation type (rename, 1:1 mapping, join, aggregation, etc.).
        2. If there are multiple source databases or tables mentioned, they most probably join together. 
        3. If there are multiple source columns, determine how they relate (e.g., concatenation, arithmetic, or join keys).
        4. This is a mapping document; do NOT use any WHERE clause in the query.
        5. Use the provided context from the knowledge base to inform your mapping.
        6. If provided, use the Transformation Specs (Type and Condition) as strong hints or requirements for the logic.
        7. If multiple databases are provided (e.g. "accounts, Task"), use them to qualify your tables if necessary or to understand the scope.
        """
        
        user_content = f"""
        Transform source column into semantic column.
        
        Source Data:
        - Subject Area: {state['source_info'].get('subject_area')}
        - Database: {state['source_info'].get('db_name')}
        - Table: {state['source_info'].get('table_name')}
        - Column: {state['source_info'].get('column_name')}
        - Datatype: {state['source_info'].get('datatype')}
        
        Target (Semantic) Data:
        - Subject Area: {state['target_info'].get('subject_area')}
        - Database: {state['target_info'].get('db_name')}
        - Table: {state['target_info'].get('table_name')}
        - Column: {state['target_info'].get('column_name')}
        - Datatype: {state['target_info'].get('datatype')}
        
        Transformation Specs (from mapping document):
        - Provided Type: {state['transformation_specs'].get('type', 'N/A')}
        - Provided Condition: {state['transformation_specs'].get('condition', 'N/A')}
        - Remarks: {state['transformation_specs'].get('remarks', 'N/A')}
        
        Knowledge Base Context:
        {state['context'] if state['context'] else "No context available."}
        
        User Feedback/Correction:
        {state.get('feedback', 'None')}
        
        Decide the appropriate transformation type and return the SQL logic.
        """
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content)
        ]
        
        # Invoke LLM with structured output
        response = structured_llm.invoke(messages)
        
        _log(f"✨ [LLM] Result: {response.transformation_type}")
        _log(f"📝 [LLM] Logic: {response.transformation_logic}")
        _log("*" * 40)
        
        return {
            "transformation_type": response.transformation_type,
            "transformation_logic": response.transformation_logic,
            "reasoning": response.reasoning
        }

    # Build the graph
    workflow = StateGraph(AgentState)
    workflow.add_node("retrieve", retrieve_context)
    workflow.add_node("generate", generate_transformation)
    
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", END)
    
    return workflow.compile()
