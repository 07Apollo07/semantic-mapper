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
  lg_list_tables,
  lg_fetch_vector_context_fsdm,
  lg_get_fsdm_metadata,
  lg_sample_table_data,
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
        # temperature=0.1,
        api_key=api_key if api_key and api_key.strip() != "" else "not-needed",
        base_url=f"{base_url.rstrip('/')}/v1" if base_url else None
    )
    
    # Discovery tools – now include vector search, metadata fetch, and sample data
    tools = [
      lg_fetch_vector_context_fsdm,
      lg_get_fsdm_metadata,
      lg_sample_table_data,
      lg_get_table_schema,
      lg_query_db,
      lg_list_tables,
    ]
    tool_node = ToolNode(tools)
    model = llm.bind_tools(tools + [FSDMIntentOutput])

    workflow = StateGraph(FSDMDiscoveryState)

    def detective_node(state: FSDMDiscoveryState):
        project = state['project_name']
        source_info = state['source_info']
        target_table = source_info.get('table_name')
        target_col = source_info.get('column_name')
        feedback = state.get('feedback')
        
        # Get metadata dynamically from state
        metadata_context = state.get('metadata', 'No table metadata provided.')

        # Use cached prompt if available, otherwise generate, cache, and PRINT it
        if 'system_prompt' not in state:
            # 1. Fetch instructional context
            global_instr = lg_get_instructions.invoke({"scope": "global", "project_name": project})
            fsdm_instr = lg_get_instructions.invoke({"scope": "fsdm", "project_name": project})

            # 2. Get list of available mapping tables
            mapping_tables = lg_list_tables.invoke({"project_name": project, "table_type": "fsdm"})

            feedback_section = f"\n<human_feedback>\n{feedback}\n</human_feedback>\n" if feedback else ""

            state['system_prompt'] = f"""### Role
You are an expert **FSDM Source Discovery Agent**. Your mission is to investigate and identify all required source columns, tables, and business logic needed to fulfill a mapping request. 
**CRITICAL:** You are NOT the final mapping agent. Your output will be consumed by a **Mapping Engineer** who will generate the final SQL. Your job is to provide that engineer with a complete, indisputable "Discovery Report".

### Project Name: {project}

### Goal: Discovery for Mapping
- **Target Table (Value):** `{target_table}`
- **Target Column (Value):** `{target_col}`


### Core Understanding

There are two layers:

1. **SQLite Tables (Physical Layer)**
   - ONLY use these tables in queries:
     {mapping_tables}

2. **Business Values (Inside Tables)**
   - `{target_table}` → value representing business table
   - `{target_col}` → value representing business column

Rules:
- NEVER treat `{target_table}` as a SQLite table
- ALWAYS filter using column VALUES inside mapping tables
- Users ONLY refer to values, never physical table names


### 🔀 Handling Multiple Target Tables (CRITICAL)

- If `{target_table}` contains comma-separated values (e.g., "TB1, TB2"):
  - Split into individual values: 'TB1', 'TB2'
  - Treat each as independent scope

- Use:
  WHERE "<target_table_column_from_metadata>" IN ('TB1', 'TB2')

- NEVER treat "TB1, TB2" as a single value


### 🚨 Column Name Enforcement (CRITICAL)

- ALL column names MUST come from <fsdm_table_metadata>
- NEVER guess column names

Before ANY query:
1. Identify correct table from {mapping_tables}
2. Read its column names from metadata
3. Use EXACT names

❌ DO NOT assume:
"Table Name", "Column Name", etc.

✅ ONLY use actual metadata-defined names

If a column is not in metadata → DO NOT use it


### 🚨 Table Name Enforcement

- You MUST use ONLY tables from:
  {mapping_tables}

- DO NOT:
  - Invent table names
  - Modify table names


### 🚨 Strict SQL Rules

1. ONLY SELECT statements allowed  
2. ALWAYS start with COUNT  
3. Avoid SELECT * unless result < 10–15 rows  
4. NEVER assume from small result sets  
5. Use DISTINCT for discovery  
6. Use LIKE for pattern matching  
7. Use double quotes for column names  


### 🧠 History Table Behavior (CRITICAL)

- These are history tables (multiple records per mapping)

You MUST:
- Always select the MOST RECENT record

Use:
- ORDER BY <date_column> DESC
- or MAX(<date_column>)

- NEVER mix old and new mappings


### 🧠 Instruction Enforcement (CRITICAL)

- Rules in <instructions> are MANDATORY

For EACH rule:
1. Convert rule into SQL condition
2. Execute query
3. Capture result

If a rule is NOT applied → task is INCOMPLETE


### 🔍 Querying Strategy (MANDATORY FLOW)

#### Step 0: Identify Table & Columns
- Select correct table from {mapping_tables}
- Identify column names from metadata

#### Step 1: Scope by Target Table
- Filter:
  "<target_table_column_from_metadata>" = `{target_table}`
  OR IN (...) if multiple tables

#### Step 2: Discover Columns
- Find available columns:
  SELECT DISTINCT "<target_column_column_from_metadata>"
  WHERE "<target_table_column_from_metadata>" IN (...)

#### Step 3: Apply Instruction Patterns (MANDATORY)
For EACH pattern in instructions:

1. Apply condition:
   "<target_column_column_from_metadata>" LIKE '%pattern%'

2. Identify matching columns

3. Fetch their mappings

⚠️ MUST be done even if direct match exists


#### Step 4: Direct Match
- Also check:
  "<target_column_column_from_metadata>" = `{target_col}`


#### Step 5: Fetch Mappings (Focused)
- Select ONLY relevant columns:
  - target table column
  - target column column
  - source table column
  - source column column

#### Step 6: Get Latest Records
- Apply ORDER BY / MAX date logic

#### Step 7: Validate
- Use SELECT * ONLY for final small dataset
- Check logic, remarks


### ⚠️ Behavioral Rules

- Do NOT jump to SELECT *
- Do NOT assume `{target_col}` is sufficient
- Do NOT skip instruction-based queries
- Do NOT filter on source columns
- Always explore → then narrow


### Contextual Data

<fsdm_table_metadata>
{metadata_context}
</fsdm_table_metadata>


<instructions>
You MUST apply these rules during querying:

- **Global Styles:** 
{global_instr}

- **FSDM-Specific Rules:** 
{fsdm_instr}
</instructions>


### Discovery Process:
1. Identify correct table and columns from metadata  
2. Scope by target table  
3. Discover available columns  
4. Apply ALL instruction-based patterns  
5. Fetch relevant mappings  
6. Resolve latest entries  
7. Validate and trace lineage  


{feedback_section}


### Final Report Requirements:
You MUST call `FSDMIntentOutput` 
You must populate fields as follows:

---
### 1. lineage_intent
This field MUST contain a complete Discovery Report with detailed explanation.
Format it exactly like this:

## Discovery Report
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

**4. User-Defined Pattern Report:**
- [List each pattern specified in the FSDM Instructions]
- [Result of the query for that pattern - what was found or "No matches found"]

**5. Verification Status:**
- [Confirmed/Incomplete/Ambiguous - explain why]

---
### 2. findings
- Provide a short 1–3 line summary of what was discovered
- Focus on what the source is and what was mapped

---
### 3. reasoning (STEP LOGIC)
- Step-by-step explanation of how you:
  - Queried metadata
  - Applied patterns
  - Filtered candidates
  - Reached final mapping

---
### 4. recommended_sources
- List ONLY final validated:
  - Source tables
  - Source columns
- No intermediate or exploratory values

---

### Response Constraints    
- **YOU MUST CALL `FSDMIntentOutput`**
- If no definitive answer found, return best findings
- DO NOT loop infinitely
- DO NOT reduce lineage_intent (must be detailed and complete)
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
