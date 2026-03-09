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
    transformation_type: str = Field(description="The category of transformation, e.g., 1:1 Mapping, Join, Aggregation, Formula, Lookup.")
    transformation_logic: str = Field(description="The specific SQL, pseudo-code, or logic for the mapping.")
    reasoning: str = Field(description="Explanation of why this mapping was chosen, citing evidence from the knowledge base context.")

# Define the state for the graph
class AgentState(TypedDict):
    source_info: Dict[str, Any]
    target_info: Dict[str, Any]
    context: str
    transformation_type: str
    transformation_logic: str
    reasoning: str
    feedback: str # Optional feedback for interactive correction

def create_agent(retriever, model_name="gpt-4o", api_key=None, base_url=None):
    """Creates the LangGraph agent."""
    
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
        
        query = f"Source: {s.get('column_name')} in {s.get('table_name')} | Target: {t.get('column_name')} in {t.get('table_name')}"
        print(f"🔍 [Agent] Retrieving context for: {query}")
        
        docs = retriever.invoke(query)
        context = "\n\n".join([doc.page_content for doc in docs])
        
        if context:
            print(f"✅ [Agent] Found {len(docs)} relevant documents.")
        else:
            print("⚠️ [Agent] No relevant context found.")
            
        return {"context": context}

    def generate_transformation(state: AgentState):
        """Generates the transformation logic based on context and input."""
        print(f"🚀 [Agent] Generating transformation for {state['source_info'].get('column_name')} -> {state['target_info'].get('column_name')}...")
        
        system_prompt = """You are a Semantic Mapper Agent. Your job is to analyze a source and target mapping and provide the transformation logic.
        Use the provided context from the knowledge base to inform your mapping.
        
        If a field is 'N/A', it means the information was not provided."""
        
        user_content = f"""
        Source Data:
        - Subject Area: {state['source_info'].get('subject_area')}
        - Database: {state['source_info'].get('db_name')}
        - Table: {state['source_info'].get('table_name')}
        - Column: {state['source_info'].get('column_name')}
        - Datatype: {state['source_info'].get('datatype')}
        
        Target Data:
        - Subject Area: {state['target_info'].get('subject_area')}
        - Database: {state['target_info'].get('db_name')}
        - Table: {state['target_info'].get('table_name')}
        - Column: {state['target_info'].get('column_name')}
        - Datatype: {state['target_info'].get('datatype')}
        
        Knowledge Base Context:
        {state['context'] if state['context'] else "No context available."}
        
        User Feedback/Correction:
        {state.get('feedback', 'None')}
        """
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content)
        ]
        
        # Invoke LLM with structured output
        response = structured_llm.invoke(messages)
        
        print(f"✨ [Agent] Transformation generated: {response.transformation_type}")
        
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
