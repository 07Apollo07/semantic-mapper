# Plan: Refactor Agent Tools

- Remove `get_tools` factory.
- Rename queries to `lg_query_db`.
- Prefix tools with `lg_` (e.g., `lg_fetch_vector_context`).
- Add `lg_get_mapping_summary`, `lg_get_fsdm_summary`, `lg_get_instructions`.
