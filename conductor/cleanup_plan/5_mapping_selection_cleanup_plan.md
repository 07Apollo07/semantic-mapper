# Mapping Selection, DB-First Preview & Persistent Instructions Plan

## 🚩 Problem Areas (Spaghetti Code Identification)
1.  **Hybrid Data Sources**: The UI currently mixes data from `st.session_state` (raw DataFrames) and SQLite. This leads to "Out of Sync" errors where the preview doesn't match the DB.
2.  **Coarse Selection**: Users can only select one "Target Table" at a time. There is no way to batch-select multiple tables or specific rows across different sheets.
3.  **Sheet Dependency**: The UI relies on the presence of the Excel file in memory for previews, making the app sluggish and memory-intensive for large files.
4.  **Inconsistent Refresh**: Changing a mapping configuration doesn't always clearly signal that the DB needs a sync before the preview is valid.
5.  **Instruction Fragmentation**: Global instructions are in `AppState`, but there is no dedicated place for FSDM-specific or Sheet-specific AI guidance.
6.  **Ephemeral Config**: If the app restarts or the session cleared, complex instructions are lost unless manually saved to a file.

## 🎯 Proposed Solution
Implement a **"DB-First" Architecture** where the SQLite database is the exclusive source for all UI previews, and introduce a granular selection mechanism for the mapping execution and  persistent **Instruction Service** for granular AI guidance.

### 1. The "DB-First" Preview
- **Eliminate `state.mapping_df`**: Once a sheet is synced to the DB, the raw DataFrame is discarded from session state.
- **Unified Preview Component**: All `st.dataframe` calls will fetch data via `ProjectManager.load_df_from_sql("mapping_sheet")`.
- **Sync Exceptions**:
    - **FSDM**: Raw files are only re-read when "Combine Header Rows" is toggled (re-syncing to DB).
    - **Mapping**: Raw files are only re-read during the "Sync to Master" operation.

### 2. Granular Selection UI (Nested Dropdown)
- **Structure**: A hierarchical selection component allowing users to pick specific files, sheets, target tables, or even individual rows for processing.
:
    - `[ ] Source File`
        - `[ ] Sheet Name`
            - `[ ] Target Table A` (Select All Rows)
                - `[ ] Row #1`
                - `[ ] Row #2`
            - `[ ] Target Table B`
- **Persistence**: The list of "Selected for Processing" rows is stored in `metadata.json` so it survives refreshes.

### 3. Persistent Instruction Management
- **New DB Table: `instructions`**:
    - `scope` (TEXT, PRIMARY KEY): 'global', 'fsdm', or 'mapping'.
    - `values` (TEXT/JSON): The actual instruction string or JSON payload.
- **Three-Tier Guidance**:
    - **Global**: Company context, business rules, and high-level mapping standards.
    - **FSDM**: Specific hints for the agent when querying the FSDM/ETL database (e.g., "Always join on AccountID").
    - **Mapping**: Sheet-specific patterns or logic for the transformation agent.

## 📝 To-Do List
- [ ] **Phase 1: Database Schema Update**
    - [ ] Audit `app.py` to identify all points where raw DataFrames are used for display.
    - [ ] Create `instructions` table in `mapping.db`.
    - [ ] Implement `ProjectManager.get_instructions(scope)` and `ProjectManager.save_instructions(scope, value)`.
- [ ] **Phase 2: UI Refactor (DB-First)**
    - [ ] Audit `app.py` and replace all raw DataFrame previews with `ProjectManager.load_df_from_sql`.
    - [ ] Remove `state.mapping_df` logic from `app.py`.
- [ ] **Phase 3: Selection Component Implementation**
    - [ ] Create `ui/selection.py` for the nested hierarchical selection tree.
    - [ ] Implement "Select All" and "Filter by Target Table" logic within the tree.
    - [ ] Update `AppState` to track `state.selected_mapping_rows` (a list of unique IDs or Row/Sheet/File combos).
    - [ ] Ensure selection state is saved to `metadata.json` via `ProjectManager`.
- [ ] **Phase 4: Instruction UI & Service**
    - [ ] Add three dedicated text areas in `app.py` for Global, FSDM, and Mapping instructions.
    - [ ] Implement auto-save to the `instructions` table on text change.
- [ ] **Phase 4: Execution Logic Update**
    - [ ] Modify the `Mapping Execution Loop` in `app.py` to iterate over the granular selection instead of just one `selected_target_table`.
    - [ ] Update `AgentExecutor` to handle the specific row context provided by the selection list.
- [ ] **Phase 5: FSDM Header Logic**
    - [ ] Implement the "Combine Rows" trigger: Re-read -> Process -> SQLite Replace -> Inventory Update.
- [ ] **Phase 5: Agent Injection**
    - [ ] Update `AgentExecutor` to fetch and inject all three instruction scopes into the system prompt at runtime.
- [ ] **Phase 6: Validation**
    - [ ] Verify that a "Hard Refresh" maintains the selected rows.
    - [ ] Confirm that previews update *only* after a Sync button is clicked.
    - [ ] Verify that instructions persist across hard refreshes and project switches.
    - [ ] Confirm the Agent correctly follows the injected FSDM and Mapping-specific hints.
