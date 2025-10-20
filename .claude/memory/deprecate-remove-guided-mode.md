# Task: Remove Guided Mode Completely

## Session Update - 2025-10-20

### Task Overview
Remove all guided mode code from Aletheia, making conversational mode the only available interaction mode. This is a breaking change that will result in v2.0.0.

### Progress So Far

#### ✅ Completed Changes
1. **Module docstring** - Updated to remove guided mode references
2. **InvestigationPhase enum** - REMOVED
3. **Class docstring** - Updated OrchestratorAgent doc to remove guided mode
4. **current_phase attribute** - REMOVED from __init__
5. **execute() method** - Updated to only support conversational mode (removed mode parameter handling)
6. **_execute_guided_mode() method** - REMOVED entirely

#### 🚧 In Progress - Orchestrator Cleanup
Need to remove the following methods and their usages:
- Line 1263: `_restore_phase_from_scratchpad()`
- Line 1291: `_display_welcome()` 
- Line 1302: `_display_phase_status()`
- Line 1428: `_route_data_collection()`
- Line 1441: `_route_pattern_analysis()`
- Line 1453: `_route_code_inspection()`
- Line 1474: `_route_root_cause_analysis()`

Also need to remove references to `self.current_phase` in:
- Line 1135: `start_session()` method
- Line 1169: Error handling logging
- Lines 1278-1313: Various phase-related methods

#### ⏭️ Remaining Tasks (From TODO)
2. Delete ui/workflow.py and update imports
3. Remove --mode flag from CLI  
4. Update config schema
5. Update session.py metadata
6. Clean up agent guided mode code
7. Remove guided prompt templates
8. Remove guided mode tests
9. Update documentation
10. Final cleanup and testing

### Files Modified So Far
- `aletheia/agents/orchestrator.py` (partially complete - ~400 LOC to remove still)

### Next Steps
1. Continue removing guided-mode methods from orchestrator.py
2. Remove all InvestigationPhase references
3. Clean up start_session() method
4. Then move to other files

### Notes
- The orchestrator.py file is 1604 lines long
- Need to be careful with method removal to avoid breaking conversational mode
- Some methods like _display_menu might be used by both modes - need to check
- Consider creating a new simplified orchestrator rather than editing in-place
