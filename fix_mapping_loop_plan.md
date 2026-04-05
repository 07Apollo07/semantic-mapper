# Plan: Fix Infinite Mapping Loop in Table Refactor

## Objective
Fix a bug where the mapping execution loop runs multiple times for a single row because the "Verify Intent" toggle UI incorrectly reverts the "Mapping Complete" status back to "Intent Verified".

## Proposed Changes

### 1. UI Status & Toggle Logic (`app.py`)
- **Fix Toggle logic:** Update the "Verify Intent" toggle to consider both `Intent Verified` and `Mapping Complete` as verified states.
- **Status Guard:** Ensure the toggle only updates the status to `Intent Verified` if it was previously `Pending`. If the status is `Mapping Complete`, the toggle should stay ON but NOT revert the status.
- **Visual Feedback:** Add status indicators (success/info/warning) to the preprocessing step to clarify the state of each row (`Ready`, `Verified`, or `Pending`).

## Verification Plan
1. **Single Row Test:** Process a table with one row. Verify that once SQL is generated, the status remains `Mapping Complete` and the execution stops.
2. **Toggle Test:** Manually toggle the intent verification and verify that the status in SQLite updates correctly between `Intent Verified` and `Pending`.
3. **Regeneration Test:** Verify that regenerating SQL correctly updates the state and persists the new result.
