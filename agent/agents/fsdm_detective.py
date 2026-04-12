from typing import TypedDict, List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from agent.agents.agents_utils import FSDMDiscoveryState, FSDMIntentOutput
from agent.tools.tools import (
    lg_get_instructions,
    lg_get_table_schema,
    lg_query_db,
    lg_list_fsdm_tables_logic
)

def should_continue(state: FSDMDiscoveryState):
    last_message = state['messages'][-1]
    if last_message.tool_calls:
        print(f"[Detective Tool Called]: {[tc['name'] for tc in last_message.tool_calls]}")
        for tc in last_message.tool_calls:
            if tc['name'] == 'FSDMIntentOutput':
                print(f"\n--- [Detective Node: Turn Input] ---")
                state['messages'][-1].pretty_print()
                print(f"[Detective Debug] FSDMIntentOutput called. Ending.")
                return "end"
        return "tools"
    print(f"[Detective Debug] No tool calls. Ending.")
    return "end"

def create_fsdm_detective(model_name="gpt-4o", api_key=None, base_url=None):
    llm = ChatOpenAI(
        model=model_name,
        temperature=0.1,
        api_key=api_key if api_key and api_key.strip() != "" else "not-needed",
        base_url=f"{base_url.rstrip('/')}/v1" if base_url else None
    )
    
    # Discovery tools
    tools = [lg_get_table_schema, lg_query_db, lg_list_fsdm_tables_logic]
    tool_node = ToolNode(tools)
    model = llm.bind_tools(tools + [FSDMIntentOutput])

    workflow = StateGraph(FSDMDiscoveryState)

    def detective_node(state: FSDMDiscoveryState):
        project = state['project_name']
        source_info = state['source_info']
        target_table = source_info.get('table_name')
        target_col = source_info.get('column_name')
        feedback = state.get('feedback')

        # Use cached prompt if available, otherwise generate, cache, and PRINT it
        if 'system_prompt' not in state:
            # 1. Fetch instructional context
            global_instr = lg_get_instructions.invoke({"scope": "global", "project_name": project})
            fsdm_instr = lg_get_instructions.invoke({"scope": "fsdm", "project_name": project})

            # 2. Get list of available mapping tables
            mapping_tables = lg_list_fsdm_tables_logic.invoke({"project_name": project})

            feedback_section = f"\n<human_feedback>\n{feedback}\n</human_feedback>\n" if feedback else ""

            state['system_prompt'] = f"""### Role
    You are an expert **FSDM Source Discovery Agent**. Your mission is to investigate and identify all required source columns, tables, and business logic needed to fulfill a mapping request. 
    **CRITICAL:** You are NOT the final mapping agent. Your output will be consumed by a **Mapping Engineer** who will generate the final SQL. Your job is to provide that engineer with a complete, indisputable "Discovery Report".

    ### Project Name: {project}

    ### SQLite Querying Nomenclature:
    1. **Physical Tables:** Use ONLY these SQLite tables in your `FROM` clause: {mapping_tables}.
    2. **Business Values:** Names like `{target_table}` or `{target_col}` are **values** inside the columns of the Documentation Tables. 
    3. **Syntax Rules:** 
       - Always use `SELECT *` when validating a candidate to see the full context (Logic, Remarks, etc.).
       - Use `LIKE '%pattern%'` for flexible column/value searches.
       - Use double quotes for identifiers if they contain spaces (e.g., `SELECT "Source Column" FROM ...`).

    ### Goal: Discovery for Mapping
    - **Target Table (Value):** `{target_table}`
    - **Target Column (Value):** `{target_col}`

    ### Discovery Process (INSTRUCTIONS ARE MANDATORY):
    1. **Execute Targeted Probes:** 
       - You MUST run at least two types of surgical queries to ensure complete discovery:
         a) **Direct Match:** Filter for exactly `TargetTable = '{target_table}'` and `TargetColumn = '{target_col}'`.
         b) **Pattern Search:** Filter for `TargetTable = '{target_table}'` and `TargetColumn LIKE '%_cd%'` (to identify code/lookup references as per instructions).
    2. **Resolve via Metadata:** 
       - If your queries return multiple rows for the same entity, use the provided `<fsdm_table_metadata>` to choose the **most recent or relevant** entry.
       - Match the findings against the subject area and description provided in the metadata to ensure the discovery makes sense.
    3. **Iterative Refinement:** 
       - Use your high turn allowance to refine SQL if your first probes fail.
       - Always **examine the entire row** (Logic, Remarks, etc.) once a candidate is found to validate the mapping.
    4. **Trace the Chain:** Follow the lineage from Target -> Source. If the Source is itself a derived value or lookup, follow that chain until you reach the final physical source.

    ### Contextual Data
    <fsdm_table_metadata>
    {state.get('metadata', 'No table metadata provided.')}
    </fsdm_table_metadata>

    <instructions>
    - **Global Styles:** {global_instr}
    - **FSDM-Specific Rules:** {fsdm_instr}
    </instructions>
    {feedback_section}

    ### Final Report Requirements:
    You MUST call `FSDMIntentOutput` with a "Discovery Report" in the `lineage_intent` field. The report should be formatted as follows:

    **1. Source Identification:**
    - Primary Source Table: [Table Name]
    - Primary Source Column: [Column Name]
    - Secondary/Lookup Sources: [Any other tables/columns involved]

    **2. Lineage Chain:**
    - [Step-by-step path from Target back to Source]

    **3. Mapping Considerations:**
    - [Any transformation logic found in the docs]
    - [Special filtering rules or constants]
    - [Business rules mentioned in instructions or metadata]

    **4. Verification Status:**
    - [Confirmed/Incomplete/Ambiguous - explain why]

    ### Response Constraints
    - **Requirement:** **YOU MUST CALL `FSDMIntentOutput` to finish your task.**

    - When using the query tool, remember u are querying a sqlite db, so format prompt accordingly.

    - If after multiple attempts u cant find the output or some definitive answer, return back your findings in the report format above; do not go in a infinite loop.
    """
            # PRINT SYSTEM PROMPT ONLY ONCE
            SystemMessage(content=state['system_prompt']).pretty_print()

        messages = state['messages']
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=state['system_prompt'])] + messages
        else:
            messages[0] = SystemMessage(content=state['system_prompt'])

        # PRETTY PRINT the input message for this turn
        print(f"\n--- [Detective Node: Turn Input] ---")
        messages[-1].pretty_print()

        response = model.invoke(messages)

        # Return system_prompt to ensure LangGraph persists it in the state
        return {"messages": [response], "system_prompt": state['system_prompt']}


    workflow.add_node("detective", detective_node)
    workflow.add_node("tools", tool_node)
    workflow.set_entry_point("detective")
    workflow.add_conditional_edges("detective", should_continue, {"tools": "tools", "end": END})
    workflow.add_edge("tools", "detective")

    return workflow.compile()
