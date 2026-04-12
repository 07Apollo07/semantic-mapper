from typing import TypedDict, List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from agent.agents.agents_utils import SemanticMappingState, MappingOutput
from agent.tools.tools import (
    lg_get_instructions,
    lg_get_table_schema,
    lg_query_db,
    lg_fetch_vector_context
)

def should_continue(state: SemanticMappingState):
    last_message = state['messages'][-1]
    if last_message.tool_calls:
        print(f"[Engineer Debug] Tool calls detected: {[tc['name'] for tc in last_message.tool_calls]}")
        for tc in last_message.tool_calls:
            if tc['name'] == 'MappingOutput':
                print(f"[Engineer Debug] MappingOutput called. Ending.")
                return "end"
        return "tools"
    print(f"[Engineer Debug] No tool calls. Ending.")
    return "end"

def create_mapping_engineer(retriever, model_name="gpt-4o", api_key=None, base_url=None):
    llm = ChatOpenAI(
        model=model_name,
        temperature=0.1,
        api_key=api_key if api_key and api_key.strip() != "" else "not-needed",
        base_url=f"{base_url.rstrip('/')}/v1" if base_url else None
    )
    
    # Engineering tools
    tools = [lg_get_table_schema, lg_query_db, lg_fetch_vector_context]
    tool_node = ToolNode(tools)
    model = llm.bind_tools(tools + [MappingOutput])

    workflow = StateGraph(SemanticMappingState)

    def retrieval_node(state: SemanticMappingState):
        """Gathers technical documentation context from the vector store."""
        s = state['source_info']
        t = state['target_info']
        
        print(f"[Engineer Debug] Starting retrieval for {s.get('table_name')} -> {t.get('table_name')}")
        
        # Build initial query for vector store context (Rich Retrieval)
        query_parts = []
        def add_parts(prefix, val):
            if not val or val == "N/A": return
            # Handle comma-separated values for joins
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

        print(f"[Engineer Debug] Vector query: {query}")
        docs = retriever.invoke(query)
        doc_context = "\n\n".join([doc.page_content for doc in docs])
        print(f"[Engineer Debug] Retrieved {len(docs)} documents.")
        return {"vector_context": doc_context}

    def engineer_node(state: SemanticMappingState):
        project = state['project_name']
        s_info = state['source_info']
        t_info = state['target_info']
        feedback = state.get('feedback')
        vector_context = state.get('vector_context', 'No additional documentation found.')
        lineage_intent = state.get('fsdm_lineage_intent', 'No lineage context provided.')
        
        print(f"[Engineer Debug] Current History: {(state['messages'])}")
        print(f"[Engineer Debug] Processing SQL mapping for {s_info.get('column_name')} in project {project}")
        
        # 1. Fetch contextual instructions
        global_instr = lg_get_instructions.invoke({"scope": "global", "project_name": project})
        mapping_instr = lg_get_instructions.invoke({"scope": "mapping", "project_name": project})
        
        feedback_section = f"\n<human_feedback>\n{feedback}\n</human_feedback>\n" if feedback else ""

        system_prompt = f"""### Role
You are an expert **SQL Engineer**. Your goal is to write a precise SQL transformation that maps source columns to a target semantic model.

### Project Name: {project}

### Target Requirement
Map source column `{s_info.get('column_name')}` from table `{s_info.get('table_name')}` 
to target column `{t_info.get('column_name')}` in table `{t_info.get('table_name')}`.

### Intelligence & Context
<fsdm_lineage_intelligence>
{lineage_intent}
</fsdm_lineage_intelligence>

<retrieved_documentation>
{vector_context}
</retrieved_documentation>

<instructions>
- **Global Style/Patterns:** {global_instr}
- **Mapping-Specific Rules:** {mapping_instr}
</instructions>
{feedback_section}

### Strict Rules
1. **Single Expression:** The transformation logic MUST be a complete, single-line SQL expression.
2. **Naming Precision:** Be exact with table and column names. Use double-quotes if names contain spaces or special characters.
3. **Tool Termination:** YOU MUST CALL `MappingOutput` to submit your final SQL transformation.

### Your Process:
1. **Intelligence Analysis:** Use `<fsdm_lineage_intelligence>` and `<retrieved_documentation>` to determine logic.
2. **Schema Verification:** Use `lg_get_table_schema` to verify actual column names in the physical database.
3. **SQL Construction:** Build the SQL expression based on requirements and verified schemas.
4. **Submission:** Call `MappingOutput` with your findings.

### Response Constraints
- **Format:** Single, concise paragraph with bullet points.
- **Content:** State the lineage hierarchy and key technical considerations.
- **Requirement:** **YOU MUST CALL `MappingOutput` to finish your task.**
"""
        messages = state['messages']
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=system_prompt)] + messages
        else:
            messages[0] = SystemMessage(content=system_prompt)
        
        response = model.invoke(messages)
        if response.content:
            print(f"[Engineer Debug] Model thoughts: {response.content}...")
            
        return {"messages": [response]}

    workflow.add_node("retrieve", retrieval_node)
    workflow.add_node("engineer", engineer_node)
    workflow.add_node("tools", tool_node)

    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "engineer")
    workflow.add_conditional_edges("engineer", should_continue, {"tools": "tools", "end": END})
    workflow.add_edge("tools", "engineer")

    return workflow.compile()
