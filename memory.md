# Project Memory: FSDM 2-Phase Agentic Workflow

## Summary of Accomplishments (Today)
- **Refactored Tools**: Streamlined agent tooling by removing the `get_tools` factory, prefixing all tools with `lg_`, and merging query functions into `lg_query_db`.
- **New Observability**: Added standard logging (print statements) to all `lg_` tools to monitor both input parameters and result snippets.
- **Improved Metadata Discovery**: Implemented targeted discovery logic in `get_mapping_summary_logic` and `get_fsdm_summary_logic` to efficiently retrieve technical metadata for specific business tables rather than dumping full documentation.
- **Workflow Orchestration**: Refactored `AgentExecutor.process_row` to implement the new 2-phase agentic workflow:
    1. **FSDM Discovery Phase**: Invokes the new `FSDM Discovery Graph` to trace source lineage.
    2. **Mapping Generation Phase**: Invokes the `Semantic Mapping Agent` using the captured lineage intent as context.
- **Context Injection**: Updated `fsdm_graph.py` to pre-fetch and inject Vector Store context, FSDM metadata, and scoped instructions into the agent's system prompt.

## Current State
- The 2-phase pipeline is structurally complete in `executor.py` and `fsdm_graph.py`.
- Tools are now highly observable and scoped.
- System prompts are rich with integrated contextual data.

## Pending Work & Future Scope
- [ ] **UI Integration**: Update `app.py` (Section 3: Transformation Results) to display the new `fsdm_lineage_intent` and `fsdm_status` fields.
- [ ] **UI Feedback Loops**: Add "Regenerate FSDM Intent" buttons to the UI to allow row-level regeneration of discovery results independently of mapping.
- [ ] **Validation Testing**: Perform full E2E validation of the 2-phase workflow from row selection to final SQL generation.
- [ ] **Instruction Persistence**: Finalize the `instructions` database table implementation for seamless global, mapping, and FSDM instruction storage and retrieval.
- [ ] **Mapping Agent Prompt Refinement**: Update the mapping agent's prompt to be as context-rich as the FSDM discovery prompt.
