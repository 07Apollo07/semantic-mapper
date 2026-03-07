from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

load_dotenv()

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
    
    # Initialize LLM with custom config
    # base_url for LangChain ChatOpenAI expects the /v1 suffix usually if it's a proxy, 
    # but the tool logic/model_fetcher.py might be providing the root. 
    # ChatOpenAI's base_url parameter typically needs the full path to the endpoint if it's not OpenAI.
    
    llm_kwargs = {
        "model": model_name,
        "temperature": 0,
    }
    if api_key:
        llm_kwargs["api_key"] = api_key
    if base_url:
        # langchain-openai expects base_url to include /v1 for most compatible APIs
        llm_kwargs["base_url"] = f"{base_url.rstrip('/')}/v1"
        
    llm = ChatOpenAI(**llm_kwargs)

    def retrieve_context(state: AgentState):
        """Retrieves relevant context from the vector store."""
        query = f"Source: {state['source_info']} | Target: {state['target_info']}"
        docs = retriever.invoke(query)
        context = "\n\n".join([doc.page_content for doc in docs])
        return {"context": context}

    def generate_transformation(state: AgentState):
        """Generates the transformation logic based on context and input."""
        system_prompt = """You are a Semantic Mapper Agent. Your job is to analyze a source and target mapping and provide the transformation logic.
        Use the provided context from the knowledge base to inform your mapping.
        
        Output format:
        Transformation Type: [e.g., 1:1 Mapping, Join, Aggregation, Formula, Lookup, etc.]
        Transformation Logic: [The SQL or pseudo-code logic]
        Reasoning: [Explanation of why this mapping was chosen based on the knowledge base]
        """
        
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
        {state['context']}
        
        User Feedback/Correction:
        {state.get('feedback', 'None')}
        """
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content)
        ]
        
        response = llm.invoke(messages)
        content = response.content
        
        # Simple parsing logic (can be improved with Structured Output)
        lines = content.split('\n')
        trans_type = "N/A"
        logic = "N/A"
        reasoning = "N/A"
        
        for line in lines:
            if line.lower().startswith("transformation type:"):
                trans_type = line.split(":", 1)[1].strip()
            elif line.lower().startswith("transformation logic:"):
                logic = line.split(":", 1)[1].strip()
            elif line.lower().startswith("reasoning:"):
                reasoning = line.split(":", 1)[1].strip()
        
        # If standard parsing fails, put full response in reasoning
        if trans_type == "N/A" and logic == "N/A":
            reasoning = content
            
        return {
            "transformation_type": trans_type,
            "transformation_logic": logic,
            "reasoning": reasoning
        }

    # Build the graph
    workflow = StateGraph(AgentState)
    workflow.add_node("retrieve", retrieve_context)
    workflow.add_node("generate", generate_transformation)
    
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", END)
    
    return workflow.compile()
