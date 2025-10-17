# REFACTOR-1: Intent-Based Orchestration (LLM-Delegated)

## Session Start - 2025-10-17

### Goal: Implement LLM-First Intent-Based Orchestration

**Task**: REFACTOR-1 from TODO.md
**Worktree**: `worktrees/feat/ref-1-intent-based`
**Branch**: `feat/ref-1-intent-based`

### Objectives

According to REFACTOR-1 in TODO.md, I need to:

1. ✅ Review existing `_execute_conversational_mode()` in OrchestratorAgent (Commit: db30977)
2. ✅ Verify `_understand_user_intent()` delegates ALL intent parsing to LLM (no custom logic)
3. ✅ Verify `_decide_next_agent()` uses LLM recommendations for routing (not hardcoded)
4. ✅ Remove any custom intent classification or routing logic from orchestrator
5. ✅ Enhance SK prompts to guide LLM in determining:
   - User intent from conversation (data collection, analysis, code inspection, diagnosis)
   - Next agent to invoke based on conversation state
   - When to ask clarifying questions vs proceed
6. ✅ Add conversation history tracking in scratchpad (already implemented)
7. ✅ Update unit tests to verify LLM receives conversation context and determines routing
8. ✅ Ensure orchestrator is thin: reads scratchpad → invokes LLM → routes based on LLM response

### Design Principles (LLM-First)

- **LLM-First Design**: ALL parameter extraction, parsing, and decision logic delegated to LLM via SK prompts
- **Plugin-Only External Calls**: Agents use plugins exclusively for kubectl, git, Prometheus HTTP APIs
- **Thin Agent Pattern**: Agents orchestrate by building prompts and invoking SK with conversation context
- **Prompt Engineering**: Focus on enhancing SK prompts to guide LLM behavior, not custom Python logic
- **No Custom Extraction**: Agents read scratchpad conversation context and pass to LLM; LLM extracts parameters

### Current State Analysis

From reviewing the code in `aletheia/agents/orchestrator.py`:

**Existing Implementation (`_understand_user_intent()`)**:
- ✅ Uses LLM to classify user intent
- ✅ Extracts parameters via LLM
- ✅ Returns JSON with intent, confidence, parameters, reasoning
- ⚠️ Uses custom intent-to-agent mapping in `_decide_next_agent()`

**Existing Implementation (`_decide_next_agent()`)**:
- ❌ **VIOLATION**: Hardcoded intent-to-agent mapping dictionary
- ❌ **VIOLATION**: Custom dependency checking logic
- Should delegate agent selection decision to LLM

**Existing Implementation (Intent Handlers)**:
- ❌ Multiple `_handle_*_intent()` methods with custom logic
- ❌ Custom state checking and response generation
- Should be unified: pass to LLM, let LLM decide

### Refactoring Plan

#### Phase 1: Enhance Prompts for LLM Decision-Making
- [ ] Update `intent_understanding` prompt to include agent routing decision
- [ ] Add prompt for "next agent selection" that considers investigation state
- [ ] Add prompt for "response generation" based on agent results

#### Phase 2: Simplify Orchestrator Logic
- [ ] Remove hardcoded intent-to-agent mapping
- [ ] Remove custom dependency checking (let LLM decide)
- [ ] Consolidate intent handlers into single LLM-based handler
- [ ] Make orchestrator purely: read context → prompt LLM → execute LLM decision

#### Phase 3: Update Tests
- [ ] Mock LLM responses for intent classification
- [ ] Mock LLM responses for agent routing decisions
- [ ] Verify orchestrator contains no custom classification logic
- [ ] Verify all routing decisions come from LLM responses

### Implementation Summary

#### Changes Made

1. **Enhanced Prompts** (`aletheia/llm/prompts.py`):
   - Added `agent_routing` system prompt for intelligent routing decisions
   - Added `agent_routing_decision` user prompt template for LLM-based routing
   - Prompts now guide LLM to check prerequisites and suggest clarifications

2. **Refactored `_decide_next_agent()`** (`aletheia/agents/orchestrator.py`):
   - **REMOVED**: Hardcoded `intent_to_agent` dictionary mapping
   - **REMOVED**: Custom `_check_agent_dependencies()` method
   - **NEW**: LLM-based routing that considers intent, confidence, conversation history, and investigation state
   - Returns structured decision: `{action, reasoning, prerequisites_met, suggested_response}`

3. **Simplified Conversational Mode Execution**:
   - Removed if/elif chain for intent handling
   - Unified execution through LLM routing decision
   - Added helper methods:
     - `_generate_clarification_response()`: LLM-generated clarifications
     - `_execute_agent_and_generate_response()`: Agent execution + LLM response generation
     - `_get_agent_results_summary()`: Brief summary for LLM context

4. **Updated Tests** (`tests/unit/test_orchestrator.py`):
   - Updated `test_decide_next_agent_*` tests to use new signature with LLM mocking
   - Removed tests for deleted `_check_agent_dependencies()` method
   - Added new tests:
     - `test_llm_based_routing_no_hardcoded_logic`: Verifies no hardcoded mappings
     - `test_llm_routing_receives_full_context`: Verifies LLM gets conversation history
   - All 54 tests passing (100%)

#### Design Compliance

✅ **LLM-First Design**: ALL routing decisions come from LLM, no hardcoded logic
✅ **Thin Agent Pattern**: Orchestrator builds prompts, invokes LLM, executes decisions
✅ **Prompt Engineering**: Decision logic in prompts, not Python code
✅ **No Custom Extraction**: Orchestrator reads context, passes to LLM; LLM decides

#### Metrics

- Tests passing: 54/54 (100%)
- Coverage: orchestrator.py now at 56.00% (was 54.15%)
- Lines of code: Orchestrator conversational logic is now fully LLM-delegated
- No hardcoded intent mappings remain

### Notes

- Successfully eliminated all hardcoded routing logic from commit db30977
- LLM now handles ALL decision-making via enhanced prompts
- Orchestrator is truly "thin" - acts as coordinator, not decision-maker
- Ready for commit and integration
