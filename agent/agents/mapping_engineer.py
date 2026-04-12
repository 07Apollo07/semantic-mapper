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
                print(f"\n--- [Engineer Node: Turn Input] ---")
                state['messages'][-1].pretty_print()
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
        
        # Extract full discovery report
        discovery = state.get('fsdm_lineage_intent', {})
        lineage_report = discovery.get('lineage_intent', 'No report provided.')
        findings = discovery.get('findings', 'N/A')
        reasoning = discovery.get('reasoning', 'N/A')
        sources = ", ".join(discovery.get('recommended_sources', [])) or 'N/A'
        
        # Use cached prompt if available, otherwise generate, cache, and PRINT it
        if 'system_prompt' not in state:
            # 1. Fetch contextual instructions
            global_instr = lg_get_instructions.invoke({"scope": "global", "project_name": project})
            mapping_instr = lg_get_instructions.invoke({"scope": "mapping", "project_name": project})
            
            feedback_section = f"\n<human_feedback>\n{feedback}\n</human_feedback>\n" if feedback else ""
            trans_specs = state.get('transformation_specs', {})

            state['system_prompt'] = f"""### Role
You are an expert **SQL Engineer**. Your goal is to write a precise SQL transformation that maps source columns to a target semantic model.

### Project Name: {project}

### 1. Core Mapping Requirements (Primary Source for SELECT)
The following information defines the base mapping logic:

**Source Information:**
- **Subject Area:** {s_info.get('subject_area', 'N/A')}
- **Database:** {s_info.get('db_name', 'N/A')}
- **Table:** {s_info.get('table_name', 'N/A')}
- **Column:** {s_info.get('column_name', 'N/A')}
- **Datatype:** {s_info.get('datatype', 'N/A')}

**Target Information:**
- **Subject Area:** {t_info.get('subject_area', 'N/A')}
- **Database:** {t_info.get('db_name', 'N/A')}
- **Table:** {t_info.get('table_name', 'N/A')}
- **Column:** {t_info.get('column_name', 'N/A')}
- **Datatype:** {t_info.get('datatype', 'N/A')}

**Transformation Specifications:**
- **Type:** {trans_specs.get('type', 'N/A')}
- **Condition:** {trans_specs.get('condition', 'N/A')}
- **Remarks:** {trans_specs.get('remarks', 'N/A')}

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
{feedback_section}

### Strict Rules
1. **Single Expression:** The transformation logic MUST be a complete, single-line SQL expression.
2. **Naming Precision:** Be exact with table and column names. Use double-quotes if names contain spaces or special characters.
3. **Tool Termination:** YOU MUST CALL `MappingOutput` to submit your final SQL transformation.

### Your Process:
1. **Base SQL:** Use the **Core Mapping Requirements** to establish the primary SELECT/Expression.
2. **Refine with Discovery:** Use the **Discovery Intelligence** to add necessary WHERE clauses, filter constants, or JOIN requirements.
3. **Schema Verification:** Use `lg_get_table_schema` to verify actual column names in the physical database.
4. **Submission:** Call `MappingOutput` with your final logic.

### Response Constraints
- **Requirement:** **YOU MUST CALL `MappingOutput` to finish your task.**
"""
            # PRINT SYSTEM PROMPT ONLY ONCE
            SystemMessage(content=state['system_prompt']).pretty_print()
        
        messages = state['messages']
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=state['system_prompt'])] + messages
        else:
            messages[0] = SystemMessage(content=state['system_prompt'])
        
        # PRETTY PRINT the input message for this turn
        print(f"\n--- [Engineer Node: Turn Input] ---")
        messages[-1].pretty_print()
        print(f"[Engineer Debug] Processing SQL mapping for {s_info.get('column_name')} in project {project}")
        
        response = model.invoke(messages)
        if response.content:
            print(f"[Engineer Debug] Model thoughts: {response.content}...")
            
        # Return system_prompt to ensure LangGraph persists it in the state
        return {"messages": [response], "system_prompt": state['system_prompt']}

    workflow.add_node("retrieve", retrieval_node)
    workflow.add_node("engineer", engineer_node)
    workflow.add_node("tools", tool_node)

    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "engineer")
    workflow.add_conditional_edges("engineer", should_continue, {"tools": "tools", "end": END})
    workflow.add_edge("tools", "engineer")

    return workflow.compile()
