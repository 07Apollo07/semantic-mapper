# Cleanup & Vector Store Refactor Plan

## 🚩 Problem Areas (Spaghetti Code Identification)
1.  **Bloated UI (`app.py`)**: At nearly 800 lines, the UI file is doing too much. It handles session state, file saving, document processing, and the complex "Sync" logic for the vector store.
2.  **Leaky Abstractions**: `VectorStoreManager` is just a thin wrapper. The actual "brains" of determining *what* to index (comparing selected vs. indexed sheets) lives inside the UI's button click handlers.
3.  **Scattered Processing**: Document processing (`pdf`, `excel`) is in `logic/document_processor.py`, but it's called directly by the UI. The Vector Store should own its own data ingestion pipeline.
4.  **Brittle Inventory**: `kb_inventory` is a passive list in session state. If the UI state gets out of sync with the actual ChromaDB collection, there's no easy way to recover.

## 🎯 Proposed Solution
Transform the Vector Store from a simple utility into a robust **Service Layer**.

### 1. New Module Structure
Move all vector-related logic into a dedicated package:
- `logic/vector_store/`
    - `__init__.py`
    - `manager.py` (The low-level ChromaDB wrapper)
    - `service.py` (The "Brains" - handles sync logic, inventory management, and ingestion)
    - `processors/` (PDF and Excel specific logic)

### 2. The "Brains" (Sync Logic)
Create a `VectorStoreService` that:
- Accepts an "Inventory" state and ensures the Vector Store matches it.
- Handles the `add_sheet`/`delete_sheet` and PDF logic internally.
- Provides a clean API for the UI (e.g., `service.sync_project(inventory)`).

## 📝 To-Do List
- [ ] **Phase 1: Research & Discovery**
    - [x] Identify problem areas in `app.py` and `logic/`.
    - [x] Map out `kb_inventory` structure.
- [ ] **Phase 2: Structural Refactor**
    - [ ] Create `logic/vector_store/` directory.
    - [ ] Move and rename `logic/vector_store.py` -> `logic/vector_store/manager.py`.
    - [ ] Extract processing logic from `logic/document_processor.py` to new module.
- [ ] **Phase 3: Service Implementation**
    - [ ] Implement `VectorStoreService` to handle the "Sync" logic.
    - [ ] Add explicit methods for `add_sheet`, `remove_sheet`, `add_pdf`, `remove_pdf`.
- [ ] **Phase 4: UI Integration**
    - [ ] Clean up `app.py` by removing manual sync loops.
    - [ ] Connect UI buttons to the new `VectorStoreService`.
- [ ] **Phase 5: Validation**
    - [ ] Test adding/deleting sheets and PDFs.
    - [ ] Verify `kb_inventory` accurately reflects the Vector Store state.
