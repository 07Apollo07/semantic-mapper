# Updated Ingestion Pipeline Refactor Plan

This plan outlines the consolidation of ingestion sections (**Section 1: Knowledge Base/Semantic** and **Section 1.2: DB Manager**) into a unified persistence architecture.

## 1. Goal
Transition from specialized/fragmented sync logic to a centralized, general-purpose synchronization and cleanup pipeline that maintains parity across three layers: Disk, Vector Store, and SQLite Database.

## 2. Refactor Strategy

### A. Generalize Database Services
- Rename/Refactor `logic/fsdm/` to `logic/db/`.
- Generalize `DBService` to handle any table prefixing, decoupling it from `FSDM/ETL_`.
- All ingestion logic (Excel -> SQL) will use this generalized service.

### B. Unified Sync & Cleanup Orchestration
- Update `ProjectManager` to serve as the single source of truth for synchronization operations.
- **`sync_to_storage`**:
    - Takes `item`, `vector_service`, `db_service`, and `prefix`.
    - Handles dual-sync (Vector + SQLite) atomicity.
    - Updates granular sync status flags (`indexed_vector`, `indexed_sql`) in metadata.
- **`cleanup_resources`**:
    - Takes `item`, `vector_service`, `db_service`, and `prefix`.
    - Atomic removal: Disk file -> DB Tables -> Vector Store indices.

### C. UI & State Standardization (`app.py`)
- Standardize the UI management components for both KB and DB Manager.
- Ensure both sections initialize items with identical tracking flags: `indexed_vector` and `indexed_sql`.
- Replace inline/fragmented loops in `app.py` with calls to the new unified `ProjectManager` methods.

## 3. Implementation Steps

1.  **Refactor `logic/fsdm/` -> `logic/db/`**: Generalize the service logic.
2.  **Update `ProjectManager`**: Implement centralized `sync_to_storage` and `cleanup_resources`.
3.  **Update `app.py`**: Refactor sync buttons and file deletion handlers to call centralized methods.
4.  **Verification**: Confirm atomic persistence (disk/DB/VS update) and atomic removal (disk/DB/VS cleanup) across both sections.

## 4. Integrity Mandates
- **No Functionality Loss**: Legacy ingestion capabilities (header merging, metadata generation) must be preserved in the refactored unified service.
- **Atomic Persistence**: Operations must track state independently (`indexed_vector`, `indexed_sql`).
- **Consistent Cleanup**: Deletion must trigger cleanup in all three locations (Disk, SQLite, Vector Store).


2 vector stores - one called semantic and another called fsdm - pending, 
test tools - pending
