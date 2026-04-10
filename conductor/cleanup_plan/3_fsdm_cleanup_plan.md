# FSDM SQLite Storage Refactor Plan

## 🚩 Problem Areas (Spaghetti Code Identification)
1.  **Direct DB Writing in UI**: The UI calls `excel_to_sqlite` directly, mixing database transaction logic with Streamlit widget handling.
2.  **Lack of Schema Discovery**: There is no dedicated service to provide the AI agent with a "map" (tables/columns) of the FSDM data, forcing it to guess or requiring hardcoded prompts.
3.  **Manual Header Preprocessing**: FSDM documents often have complex multi-row headers. Currently, this is either ignored or handled inconsistently.
4.  **Brittle Sync**: `fsdm_inventory` is a passive list. If a table is deleted in SQLite but remains in the list, the app crashes or shows ghost data.

## 🎯 Proposed Solution
Transform FSDM management into a robust **Service Layer** that handles the lifecycle of structured data from upload to AI-ready schema.

### 1. New Module Structure
- `logic/fsdm/`
    - `__init__.py`
    - `service.py` (The "Brains" - manages uploads, preprocessing, and DB operations)
    - `query_engine.py` (Handles AI-driven queries against the SQLite DB)

### 2. The "Brains" (Key Functions)
- **`preprocess_sheet(file_bytes, combine_headers=True)`**: 
    - Takes raw bytes from an Excel sheet.
    - If `combine_headers` is checked in UI, merges the first two rows to create unique, descriptive column names.
    - Returns a cleaned pandas DataFrame.
- **`sync_fsdm_table(project_name, sheet_name, df)`**:
    - Handles the `CREATE TABLE`, `INSERT`, or `DROP TABLE` operations.
    - Ensures the `fsdm_inventory` correctly reflects the actual tables in `mapping.db`.
- **`get_fsdm_schema(project_name)`**:
    - Returns a JSON-ready map of all uploaded FSDM tables and their column names.
    - This will be the primary context provider for the LLM when it needs to "see" the target model.

## 📝 To-Do List
- [ ] **Phase 1: Research & Setup**
    - [ ] Create `logic/fsdm/` package.
    - [ ] Map all existing `ProjectManager.save_df_to_sql` calls in `app.py`.
- [ ] **Phase 2: Preprocessing Engine**
    - [ ] Implement `preprocess_sheet` with multi-row header support.
    - [ ] Add unit tests for different Excel header formats.
- [ ] **Phase 3: Service Implementation**
    - [ ] Implement `FSDMService.upload_to_db` (Save to FS -> Preprocess -> SQLite).
    - [ ] Implement `get_fsdm_schema` for LLM discovery.
    - [ ] Implement explicit `delete_table` and `query_table` methods.
- [ ] **Phase 4: UI Integration**
    - [ ] Add "Combine Header Rows" checkbox to the FSDM upload section in `app.py`.
    - [ ] Replace manual `excel_to_sqlite` calls with `FSDMService.sync()`.
- [ ] **Phase 5: Validation**
    - [ ] Verify FSDM tables are correctly created in `mapping.db`.
    - [ ] Test the Agent's ability to retrieve schema via the new service.
