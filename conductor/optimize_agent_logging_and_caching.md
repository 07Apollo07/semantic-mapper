# Plan: Optimize Agent Thought Process and Reduce Redundant Instruction Fetching

## Objective
1.  **Refine Agent Logging:** Modify the `detective_node` and `engineer_node` to print only the latest message being sent to the LLM (for debugging) instead of the entire chat history.
2.  **Optimize Instruction Fetching:** Implement a mechanism to fetch `lg_get_instructions` only once or cache them, rather than invoking them on every step of the graph execution.
3.  **Encapsulate Prompt Creation:** Create a `make_prompt` helper function to generate the system prompt once and cache it, ensuring the agent uses this cached variable on subsequent steps.

## Key Files & Context
- `agent/agents/fsdm_detective.py`
- `agent/agents/mapping_engineer.py`

## Implementation Steps
1.  **Logging Optimization**:
    - Modify `detective_node` and `engineer_node` in the respective files.
    - Change `print(f"[...] Current History: {state['messages']}")` to print only the latest message: `print(f"[...] Latest Message: {state['messages'][-1]}")`.

2.  **Instruction & Prompt Caching**:
    - Extract system prompt generation into a `make_prompt` function.
    - Modify the workflow to store the generated prompt in the `state` object or use a memoization pattern, so that it is computed once and re-used for the duration of the task.

## Verification
- Monitor console logs during agent execution.
- Verify that system prompt generation (`make_prompt`) and instruction fetching occur only once per task execution.
