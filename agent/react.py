from typing import Dict, Any, List, Optional
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from pydantic import BaseModel, Field
import json

class TransformationOutput(BaseModel):
    transformation_type: str = Field(description="Type of transformation: e.g., 1:1 mapping, rename, Left-Join, Right join, Outer Join, Inner Join, aggregation etc.")
    transformation_logic: str = Field(description="The complete single-line SQL transforming source column(s) to the target semantic column.")
    reasoning: str = Field(description="Short explanation why this transformation is needed, citing evidence from context.")

def create_react_agent_runnable(retriever, model_name="gpt-4o", api_key=None, base_url=None, log_callback=None):
    """Creates a ReAct agent using the new LangChain create_agent API."""
    
    def _log(msg):
        if log_callback:
            log_callback(msg)
        print(msg)

    llm = ChatOpenAI(
        model=model_name,
        temperature=0,
        api_key=api_key if api_key and api_key.strip() != "" else "not-needed",
        base_url=f"{base_url.rstrip('/')}/v1" if base_url else None
    )

    @tool
    def search_kb(query: str) -> str:
        """Useful for searching the Knowledge Base for documentation, column descriptions, and business logic related to source or target columns."""
        _log(f"🔍 [ReAct Tool] Searching KB for: {query}")
        docs = retriever.invoke(query)
        context = "\n\n".join([doc.page_content for doc in docs])
        _log(f"✅ [ReAct Tool] Found {len(docs)} snippets.")
        return context

    tools = [search_kb]

    system_prompt = """You are an expert SQL generator. Your job is to analyze source and target mappings and provide the transformation logic.
    Always Use the SearchKnowledgeBase tool to get more information about specific columns, tables, or business rules.
    
    Guidelines:
    1. Decide the appropriate transformation type (rename, 1:1 mapping, join, aggregation, etc.).
    2. If there are multiple source databases or tables mentioned, they most probably join together. 
    3. If there are multiple source columns, determine how they relate (e.g., concatenation, arithmetic, or join keys).
    4. This is a mapping document; do NOT use any WHERE clause in the query.
    5. Use the provided context from the knowledge base and any information you find via tools to inform your mapping.
    6. Use the Transformation Specs (Type and Condition) as strong hints or requirements for the logic.
    """

    # Create the agent graph
    agent_graph = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
        response_format=TransformationOutput
    )

    class ReActWrapper:
        def invoke(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
            s = inputs['source_info']
            t = inputs['target_info']
            spec = inputs['transformation_specs']
            
            user_content = f"""
            Transform source column into semantic column.
            
            Source Data:
            - Subject Area: {s.get('subject_area')}
            - Database: {s.get('db_name')}
            - Table: {s.get('table_name')}
            - Column: {s.get('column_name')}
            - Datatype: {s.get('datatype')}
            
            Target (Semantic) Data:
            - Subject Area: {t.get('subject_area')}
            - Database: {t.get('db_name')}
            - Table: {t.get('table_name')}
            - Column: {t.get('column_name')}
            - Datatype: {t.get('datatype')}
            
            Transformation Specs:
            - Provided Type: {spec.get('type', 'N/A')}
            - Provided Condition: {spec.get('condition', 'N/A')}
            - Remarks: {spec.get('remarks', 'N/A')}
            
            Initial Knowledge Base Context:
            {inputs.get('context', 'No initial context available.')}
            
            User Feedback/Correction:
            {inputs.get('feedback', 'None')}
            """
            
            # The new agent graph expects a list of messages or a dict with "messages"
            result = agent_graph.invoke({"messages": [{"role": "user", "content": user_content}]})
            
            # In the new API, the structured response is usually in the state
            # and potentially the last message if CompiledStateGraph returns it.
            # Based on factory.py, it returns CompiledStateGraph[AgentState[ResponseT], ...]
            # Let's extract the response.
            
            # If the output format is returned in the 'structured_response' key (if standard),
            # or in 'response' key (if configured that way).
            
            # Since create_agent returns a graph, the invoke result is the state.
            # We need to find the structured output in the state.
            
            # Check for 'structured_response' key first (common in some implementations)
            if "structured_response" in result:
                 response = result["structured_response"]
                 return {
                    "transformation_type": response.transformation_type,
                    "transformation_logic": response.transformation_logic,
                    "reasoning": response.reasoning
                }
            
            # Fallback: check if the last message has the structured output
            messages = result.get("messages", [])
            if messages:
                last_msg = messages[-1]
                # Sometimes the structured output is attached to the last message
                if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                     # If the LLM used a tool call to return the structure
                     pass
                
            # Fallback: check if the 'response' key exists
            if "response" in result:
                 response = result["response"]
                 if isinstance(response, TransformationOutput):
                     return {
                        "transformation_type": response.transformation_type,
                        "transformation_logic": response.transformation_logic,
                        "reasoning": response.reasoning
                    }

            return {
                "transformation_type": "ReAct Output",
                "transformation_logic": "See reasoning",
                "reasoning": f"Agent finished. Result keys: {list(result.keys())}"
            }

    return ReActWrapper()
