# Mapping Service & Multi-Sheet Refactor Plan

## 🚩 Problem Areas (Spaghetti Code Identification)
1.  **Single Sheet Limitation**: The current implementation only supported a single sheet from a single uploaded Excel file.
2.  **Volatile State**: Mapping data was held as a `pd.DataFrame` in session state, making it brittle across refreshes.
3.  **UI-Driven Logic**: Logic for filtering columns and rebuilding SQLite was mixed with Streamlit widgets.
4.  **No Lineage**: Lack of record of source file/sheet lineage in the database.

## 🎯 Proposed Solution
Transform mapping management into a robust **Mapping Service Layer** that supports multi-sheet uploads, granular per-sheet configuration, and DB-first previews.

### 1. New Module Structure
- `logic/mapping/`
    - `service.py`: Handles sheet normalization and database synchronization.
    - `config.py`: Contains `MappingConfig` dataclass with per-sheet settings (including data start row).

### 2. Key Features
- **Mapping Manager Dashboard**: Supports multi-file uploads and per-sheet configuration expanders.
- **Granular Syncing**: Each sheet has its own sync status ("Pending"/"Synced") and can be previewed directly from its dedicated SQLite table.
- **Normalization Engine**: `MappingService` now uses `data_start_row` and user-defined column identifiers to extract and normalize data, setting consistent internal headers for downstream joins.
- **Persistence**: Inventory and configurations are automatically saved to `metadata.json`.

## 📝 Status
- [x] **Phase 1: Research & Structure**: Created `logic/mapping/` packages and defined `MappingConfig`.
- [x] **Phase 2: Mapping Service Implementation**: Implemented `normalize_sheet` (supporting `data_start_row` and column mapping) and `sync_sheet`/`sync_mappings` for DB storage.
- [x] **Phase 3: UI Integration**: Implemented the "Mapping Manager" dashboard in `app.py`, including per-sheet configuration, "Data Row Start" input, and sync/preview triggers.
- [ ] **Phase 4: Agent Compatibility**: Update `AgentExecutor` and `ProjectManager` to point to the new consolidated table.
- [ ] **Phase 5: Validation**: Comprehensive E2E testing (multi-file sync, data row start accuracy, and agent schema discovery).
