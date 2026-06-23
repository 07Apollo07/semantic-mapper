# Default Agent Improvement Plan

Below is a concise, step‑by‑step plan for extending the **default agent** so that it can:

1. **Read the mapping Excel sheet** (target → source triples).  
2. **Discover the full lineage of the source table** (`T2`) inside the FSDM knowledge base.  
3. **Pass that lineage report to the Mapping Engineer** so it can generate a single SQL statement that maps the source column (`C2`) onto the target column (`C1`) while also pulling in any additional columns from the target table (`T1`) and adding the appropriate `WHERE` clauses.

---

## 1️⃣ Data‑flow Overview (what already exists)

| Component | Current Role | What we’ll add |
|-----------|---------------|----------------|
| **`app.py` → UI** | Uploads Excel sheets → stores them in `state.mapping_inventory` | Parse each sheet into the *standard mapping config* (already done) |
| **`AgentExecutor.process_row`** | Calls **FSDM Detective** → **Mapping Engineer** | Pass **source‑table name (`T2`)** and **target‑table name (`T1`)** plus the *full mapping spec* (`DB, T1, C1, DB2, T2, C2`) |
| **`fsdm_detective.py`** | Uses SQL tools (`lg_get_table_schema`, `lg_query_db`, `lg_list_tables`) | Add **vector‑search tools** (`lg_fetch_vector_context_fsdm`, `lg_get_fsdm_metadata`, `lg_sample_table_data`) and accept **`transformation_specs`** and **`physical_source_info`** |
| **`mapping_oneshot.py`** (one‑shot engineer) | Generates SQL from LLM only (no tools) | Include **`physical_source_info`** in the prompt, and optionally switch to the *tool‑enabled* `mapping_engineer.py` so the engineer can verify column names with `lg_get_table_schema` |

---

## 2️⃣ Concrete Changes Needed

### 2.1 Extend the **row‑level payload** (`row_data`)

When the UI builds `row_data` (see `app.py` → “Processing Row Mappings”), add the **source‑table name** (`source_table`) and **source‑column name** (`source_col`) *as they appear in the Excel sheet*:

```python
row_data = {
    "source_info": {
        "db_name": source_db,          # DB2
        "table_name": source_table,   # T2
        "column_name": source_col,    # C2
        ...
    },
    "target_info": {
        "db_name": target_db,          # DB
        "table_name": target_table,    # T1
        "column_name": target_col,     # C1
        ...
    },
    "physical_source_info": {          # optional – keep if you have a physical‑source sheet
        "db_name": ..., "table_name": ..., "column_name": ...
    },
    "transformation_specs": {
        "type": state.map_trans_type,
        "condition": state.map_trans_cond,
        "remarks": state.map_remarks,
    },
    "target_table": target_table
}
```
*Why?* The Detective will now know exactly which source table (`T2`) it must trace inside the FSDM docs.

### 2.2 Give the **FSDM Detective** the right tools

Edit **`agent/agents/Row/Defaults/fsdm_detective.py`** (or the wrapper that creates the graph) to include the following tools:

```python
from agent.tools.tools import (
    lg_fetch_vector_context_fsdm,
    lg_get_fsdm_metadata,
    lg_sample_table_data,
    lg_get_table_schema,
    lg_query_db,
    lg_list_tables,
)
```
Replace the current `tools = [lg_get_table_schema, lg_query_db, lg_list_tables]` with:

```python
tools = [
    lg_fetch_vector_context_fsdm,   # semantic search over FSDM docs
    lg_get_fsdm_metadata,          # raw metadata for a specific table
    lg_sample_table_data,          # peek at real rows (helps with WHERE clauses)
    lg_get_table_schema,           # verify column names
    lg_query_db,                   # run ad‑hoc SELECTs
    lg_list_tables,
]
```
*Result:* The Detective can now:

* **Search** the FSDM vector store for “`T2`” and retrieve definition, lineage, and any business rules.
* **Pull** the exact `CREATE TABLE` statement for `T2` (or any related FSDM tables).
* **Sample** a few rows to infer typical values for filters (`WHERE` clauses).

### 2.3 Pass **transformation specs** and **physical source info** to the Detective

In `default.py → process_row()` (the wrapper that builds `fsdm_inputs`) add the extra fields:

```python
fsdm_inputs = {
    "source_info": source_info,
    "target_info": row_data.get('target_info', {}),
    "fsdm_instructions": "",
    "metadata": metadata,
    "project_name": self.state.current_project,
    "messages": [...],
    "transformation_specs": row_data.get('transformation_specs', {}),
    "physical_source_info": row_data.get('physical_source_info', {}),
    "feedback": feedback,
}
```
Update the `FSDMDiscoveryState` definition (in `agents_utils.py`) to include these new keys:

```python
class FSDMDiscoveryState(TypedDict):
    ...
    transformation_specs: Dict[str, Any]
    physical_source_info: Dict[str, Any]
    ...
```
*Why?* The Detective can now tailor its queries (e.g., “look for joins on `T2` where `condition` = …”) and embed physical‑source constraints.

### 2.4 Enrich the **Mapping Engineer** prompt

If you stay with the **one‑shot** engineer (`mapping_oneshot.py`), simply inject the new fields into the user message:

```python
user_content = f"""
...
Transformation Specs:
- Type: {trans_specs.get('type', 'N/A')}
- Condition: {trans_specs.get('condition', 'N/A')}
- Remarks: {trans_specs.get('remarks', 'N/A')}

Physical Source (if any):
{ps_info}
...
"""
```
If you prefer the **tool‑enabled** engineer (`mapping_engineer.py`), you can keep the existing prompt but now the `state` already contains `fsdm_lineage_intent` (full discovery report) plus the extra specs, so no change is required.

### 2.5 (Optional) Switch to the **tool‑enabled engineer**

The one‑shot engineer cannot verify column names. To give it that safety net, replace the call in `default.py`:

```python
self.mapping_engineer = create_mapping_oneshot(...)
```
with:

```python
self.mapping_engineer = create_mapping_engineer(
    retriever=self.state.v_manager.get_retriever(),
    model_name=llm_config["model_name"],
    api_key=llm_config["api_key"],
    base_url=llm_config["base_url"],
    log_callback=self._log,
)
```
The `create_mapping_engineer` graph already contains `lg_get_table_schema` and `lg_query_db`, so the engineer can double‑check that the columns it references actually exist.

---

## 3️⃣ Checklist for Implementation

| ✅ | Item |
|----|------|
| ☐ | Add the three new tools (`lg_fetch_vector_context_fsdm`, `lg_get_fsdm_metadata`, `lg_sample_table_data`) to the Detective’s tool list. |
| ☐ | Extend `FSDMDiscoveryState` with `transformation_specs` and `physical_source_info`. |
| ☐ | Modify `default.py → process_row()` to include those fields in `fsdm_inputs`. |
| ☐ | Ensure the UI (`app.py` → row‑payload builder) populates `source_info`, `target_info`, `transformation_specs`, and `physical_source_info` from the mapping sheet. |
| ☐ | (Optional) Switch the engineer from `create_mapping_oneshot` to `create_mapping_engineer` for tool‑enabled verification. |
| ☐ | Test end‑to‑end: upload a sheet with `DB, T1, C1, DB2, T2, C2`; run a single row mapping; verify that the generated SQL contains the target table, source column, and a `WHERE` clause derived from the FSDM discovery. |
| ☐ | Add unit tests in `test_tools.py` / `test_prompt.py` that mock a simple FSDM table (`T2`) and assert that the Detective’s output includes the expected lineage fields. |

---

## 4️⃣ Next Steps

1. **Confirm** which of the above changes you’d like to apply first (e.g., just the tool addition, or the full switch to the tool‑enabled engineer).  
2. I can **apply the patches** using `apply_patch` for the selected files.  
3. After the patches, we’ll **run the app**, upload a tiny test sheet, and verify that the generated SQL looks as expected.  

Let me know which subset you want me to implement, or if you need any clarification on any of the steps!