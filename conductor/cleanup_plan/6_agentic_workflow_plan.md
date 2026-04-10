# 2-Phase Agentic Workflow & Persistence Plan

## 🚩 Problem Areas (Spaghetti Code Identification)
1.  **Monolithic Agent**: Current `AgentExecutor` attempts to do discovery and mapping in one go, leading to mixed context and lower accuracy.
2.  **Disconnected Persistence**: `final_mappings` stores results, but doesn't clearly separate the "FSDM Discovery" from the "Final Mapping" logic, making it hard to regenerate just one part.
3.  **Context Bloat**: Passing all instructions (Global + FSDM + Mapping) to a single prompt confuses the agent about its current objective.
4.  **Lack of Tool Validation**: No automated way to verify if the DB Query tools are fetching the correct schema before the agent starts "thinking."

## 🎯 Proposed Solution
Implement a **2-Phase LangGraph Workflow** that separates Discovery (FSDM Agent) from Implementation (Mapping Agent), with persistent state at every step.

### 1. Phase 1: FSDM Discovery Agent (ReAct)
- **Objective**: Identify the lineage from raw FSDM sources to the mapping source columns.
- **Context**: 
    - FSDM-specific instructions.
    - Schema of `fsdm_etl_...` tables.
- **Output**: `fsdm_lineage_intent` (How data reached the mapping source).
- **Storage**: Commits to `final_mappings.fsdm_intent`.

### 2. Phase 2: Semantic Mapping Agent
- **Objective**: Generate final transformation SQL.
- **Context**:
    - Global + Mapping-specific instructions.
    - Vector Store (Business definitions/KB).
    - Output from Phase 1 (The "Discovery Link").
    - `mapping_sheet` table query tool.
- **Output**: Pydantic structure (SQL, Reasoning, Transformation Type).
- **Storage**: Commits to `final_mappings.mapping_logic`.

### 3. Persistent "Lifetime" UI
- **Row-Level Awareness**: When the user selects a range, the UI checks `final_mappings`. 
    - If data exists: Show "Draft" (Discovery/Logic) with individual **Regenerate** buttons.
    - If not: Show **Generate** button.
- **Append-Only Upsert**: New selections are merged into the persistent table, never overwriting manual corrections unless requested.

## 📝 To-Do List
- [ ] **Phase 1: Database Schema Expansion**
    - [ ] Update `final_mappings` table to include `fsdm_intent`, `fsdm_status`, `mapping_status`.
- [ ] **Phase 2: Specialized Agents (LangGraph)**
    - [ ] Implement `agent/fsdm_agent.py`: Specialized for lineage discovery.
    - [ ] Implement `agent/mapping_agent.py`: Specialized for SQL generation.
    - [ ] Define the LangGraph in `agent/graph.py` to chain these two agents.
- [ ] **Phase 3: Tooling & Context Builder**
    - [ ] Create a `ContextBuilder` to aggregate Vector Store + DB Schema + Instructions based on the current phase.
    - [ ] Create `logic/tools.py` with validated SQLite query tools.
- [ ] **Phase 4: UI Integration (Dual-Regen)**
    - [ ] Update Section 3 in `app.py` to show both FSDM Intent and Mapping Logic.
    - [ ] Add `Regenerate FSDM Intent` button (triggers Phase 1).
    - [ ] Add `Regenerate Mapping` button (triggers Phase 2 with existing Phase 1 output).
- [ ] **Phase 5: Automated Testing**
    - [ ] Create `tests/test_agent_tools.py` to verify:
        - DB tools return correct row counts for `fsdm_etl_` tables.
        - Vector Store tool returns relevant hits for mapping keywords.
        - Context builder correctly assembles instructions.
- [ ] **Phase 6: Validation**
    - [ ] End-to-end test: Select row -> Discovery -> Mapping -> View in UI.
    - [ ] Test persistence: Close app -> Reopen -> Row shows previous "Discovery Link".
