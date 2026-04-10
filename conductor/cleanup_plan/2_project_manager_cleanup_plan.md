# Project Manager (Persistence Layer) Refactor Plan

## 🚩 Problem Areas (Spaghetti Code Identification)
1.  **State Fragmentation**: Project state is scattered across `state.py` (session state), `metadata.json` (disk), and `mapping.db` (disk). 
2.  **Manual Persistence**: Developers must remember to call `state.save_project()` or `ProjectManager.update_metadata()` after every change, leading to "save-missing" bugs.
3.  **Passive Inventory**: The `kb_inventory` and `fsdm_inventory` are treated as simple lists rather than managed resources that represent the project's source of truth.

## 🎯 Proposed Solution
Consolidate `ProjectManager` into a formal **Persistence Layer**. Its sole responsibility is to ensure the project "heartbeat" remains consistent across reloads.

### 1. Role & Responsibility
The `ProjectManager` will act as the single entry point for:
- **Project State**: Loading/Saving everything from `metadata.json` (Global instructions, column mappings, UI toggles).
- **Inventory Synchronization**: Ensuring that what the user sees in the UI matches what is actually stored on disk and in the databases.
- **Data Integrity**: Managing the project folder structure and the health of the `mapping.db`.

### 2. Key Refactor Points
- **Centralized "Save"**: Move all `st.session_state` updates that require persistence into a single `ProjectManager.persist(state)` method.
- **Human Input Capture**: Explicitly save all human-provided metadata (like "Target Table to Process" or "Global Instructions") automatically.
- **Mapping Persistence**: When the AI generates a mapping or a human corrects it, the `ProjectManager` ensures this is committed to the SQLite DB immediately.

## 📝 To-Do List
- [ ] **Phase 1: State Consolidation**
    - [ ] Review `logic/state.py` and identify all fields that must survive a refresh.
    - [ ] Update `metadata.json` schema to include all UI configuration inputs.
- [ ] **Phase 2: Inventory Management**
    - [ ] Refactor `kb_inventory` to be a managed property that auto-saves to `metadata.json` on change.
    - [ ] Ensure file paths in inventory are always relative to the project root.
- [ ] **Phase 3: Persistence API**
    - [ ] Implement `ProjectManager.rehydrate(project_name)` to load a complete state in one call.
    - [ ] Create `ProjectManager.save_mapping_result()` to centralize SQLite mapping writes.
- [ ] **Phase 4: UI Cleanup**
    - [ ] Remove redundant `save_file` and `update_metadata` calls scattered throughout `app.py`.
    - [ ] Initialize the project using the new `rehydrate` logic.
- [ ] **Phase 5: Validation**
    - [ ] Perform "Hard Refresh" tests: Modify settings, refresh browser, verify settings persist.
    - [ ] Verify that deleting a project clean up all associated SQLite tables and files.
