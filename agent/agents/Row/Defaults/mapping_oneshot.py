from typing import TypedDict, List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, END
from agent.agents.agents_utils import SemanticMappingState, MappingOutput
from agent.tools.tools import lg_get_instructions
import json

def create_mapping_oneshot(retriever, model_name="gpt-4o", api_key=None, base_url=None, log_callback=None):
    """Creates a one-shot LangGraph agent for SQL mapping."""
    
    def _log(msg):
        if log_callback:
            log_callback(msg)
        print(msg)

    # Initialize the LLM with custom config
    llm = ChatOpenAI(
        model=model_name,
        temperature=0.2,
        api_key=api_key if api_key and api_key.strip() != "" else "not-needed",
        base_url=f"{base_url.rstrip('/')}/v1" if base_url else None
    )

    # Wrap LLM with structured output to match MappingOutput schema
    structured_llm = llm.with_structured_output(MappingOutput)

    def retrieve_context(state: SemanticMappingState):
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
        else:
            _log("⚠️ [Retriever] No relevant context found.")
            
        return {"vector_context": context}

    def generate_transformation(state: SemanticMappingState):
        """Generates the transformation logic based on context and input."""
        project = state['project_name']
        s_info = state['source_info']
        t_info = state['target_info']
        trans_specs = state.get('transformation_specs', {})
        vector_context = state.get('vector_context', 'No context available.')
        feedback = state.get('feedback', 'None')
        
        # Extract discovery intelligence
        discovery = state.get('fsdm_lineage_intent', {})
        lineage_report = discovery.get('lineage_intent', 'No report provided.')
        findings = discovery.get('findings', 'N/A')
        reasoning = discovery.get('reasoning', 'N/A')
        sources = ", ".join(discovery.get('recommended_sources', [])) if isinstance(discovery.get('recommended_sources'), list) else str(discovery.get('recommended_sources', 'N/A'))

        # Fetch contextual instructions
        global_instr = lg_get_instructions.invoke({"scope": "global", "project_name": project})
        mapping_instr = lg_get_instructions.invoke({"scope": "mapping", "project_name": project})

        _log(f"🚀 [LLM] Generating SQL transformation for {s_info.get('column_name')} -> {t_info.get('column_name')}...")
        
        system_prompt = """You are an expert SQL generator. Your job is to analyze source and target mappings and provide the transformation logic.
Return a single-line SQL statement that transforms the source column(s) to the target semantic column.

Important Guidelines:
1. Decide the appropriate transformation type (rename, 1:1 mapping, join, aggregation, etc.).
2. If there are multiple source databases or tables mentioned, they most probably join together. 
3. If there are multiple source columns, determine how they relate (e.g., concatenation, arithmetic, or join keys).
4. This is a mapping document; do NOT use any WHERE clause in the query UNLESS specifically identified by Discovery Intelligence as a mandatory filtering rule for the source scope.
5. Use the provided context from the knowledge base to inform your mapping.
6. If provided, use the Transformation Specs (Type and Condition) as strong hints or requirements for the logic.
7. If multiple databases are provided (e.g. "accounts, Task"), use them to qualify your tables if necessary or to understand the scope.
"""
        # PRINT SYSTEM PROMPT
        print(f"\n--- [Mapping One-Shot: System Prompt] ---")
        SystemMessage(content=system_prompt).pretty_print()

        user_content = f"""
Transform source column into semantic column.

Source Data:
- Subject Area: {s_info.get('subject_area')}
- Database: {s_info.get('db_name')}
- Table: {s_info.get('table_name')}
- Column: {s_info.get('column_name')}
- Datatype: {s_info.get('datatype')}

Target (Semantic) Data:
- Subject Area: {t_info.get('subject_area')}
- Database: {t_info.get('db_name')}
- Table: {t_info.get('table_name')}
- Column: {t_info.get('column_name')}
- Datatype: {t_info.get('datatype')}

Transformation Specs (from mapping document):
- Provided Type: {trans_specs.get('type', 'N/A')}
- Provided Condition: {trans_specs.get('condition', 'N/A')}
- Remarks: {trans_specs.get('remarks', 'N/A')}

### 2. Discovery Intelligence (Source for WHERE/JOIN/CONSIDERATIONS)
Use the following report from the Discovery Agent to identify filtering rules (WHERE clauses), lookup tables (JOINS), and specific business logic constants:

<fsdm_discovery_report>
{lineage_report}
</fsdm_discovery_report>

<fsdm_discovery_findings>
- **Summary:** {findings}
- **Logical Reasoning:** {reasoning}
- **Identified Source Entities:** {sources}
</fsdm_discovery_findings>

<retrieved_documentation>
{vector_context}
</retrieved_documentation>

<instructions>
- **Global Style/Patterns:** {global_instr}
- **Mapping-Specific Rules:** {mapping_instr}
</instructions>

User Feedback/Correction:
{feedback}

Decide the appropriate transformation type and return the SQL logic.
"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content)
        ]
        
        # PRETTY PRINT the final input message
        print(f"\n--- [Mapping One-Shot: Turn Input] ---")
        messages[-1].pretty_print()

        # Invoke LLM with structured output
        response = structured_llm.invoke(messages)
        
        _log(f"✨ [LLM] Result: {response.transformation_type}")
        _log(f"📝 [LLM] Logic: {response.transformation_logic}")
        _log("*" * 40)
        
        # Create an AIMessage with a tool call to MappingOutput to satisfy AgentExecutor
        tool_call_id = "call_" + str(hash(response.transformation_logic))[-10:]
        ai_message = AIMessage(
            content="",
            tool_calls=[{
                "name": "MappingOutput",
                "args": {
                    "transformation_type": response.transformation_type,
                    "transformation_logic": response.transformation_logic,
                    "reasoning": response.reasoning
                },
                "id": tool_call_id
            }]
        )
        
        return {
            "transformation_type": response.transformation_type,
            "transformation_logic": response.transformation_logic,
            "reasoning": response.reasoning,
            "messages": [ai_message]
        }

    # Build the graph
    workflow = StateGraph(SemanticMappingState)
    workflow.add_node("retrieve", retrieve_context)
    workflow.add_node("generate", generate_transformation)
    
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", END)
    
    return workflow.compile()
