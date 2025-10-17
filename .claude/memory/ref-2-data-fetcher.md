# Session Update - 2025-10-17 (Conversational Data Fetcher Implementation)

## Task: REFACTOR-2 - Update Data Fetcher for Conversational Mode

**Status**: 🔄 IN PROGRESS

**Worktree**: `worktrees/feat/ref-2-data-fetcher`
**Branch**: `feat/ref-2-data-fetcher`

---

## Objectives (from TODO.md)

Update Data Fetcher Agent to support conversational mode using LLM-delegated parameter extraction:

1. ✅ Enhance `_build_sk_prompt()` to include full `CONVERSATION_HISTORY` section from scratchpad
2. ✅ Add conversational prompt templates instructing LLM to extract K8s/Prometheus parameters from conversation
3. ✅ LLM determines pod name, namespace, service name, time ranges from conversational context
4. ✅ LLM uses `KubernetesPlugin` and `PrometheusPlugin` via `FunctionChoiceBehavior.Auto()`
5. ✅ If parameters missing, LLM generates clarifying questions (no custom extraction logic)
6. ⏳ Update unit tests to verify LLM receives conversation context and invokes correct plugins

**Acceptance Criteria**: Data Fetcher delegates ALL parameter extraction to LLM; agent contains no custom extraction logic

---

## Implementation Plan

### Phase 1: Add Conversational Prompt Templates ✅
- [ ] Create `data_fetcher_conversational` system prompt in `prompts.py`
- [ ] Create `data_fetcher_conversational_collection` user prompt template
- [ ] Templates instruct LLM to:
  - Read conversation history for context
  - Extract parameters from natural language
  - Use plugins for actual data collection
  - Generate clarifying questions when parameters missing

### Phase 2: Update `_build_sk_prompt()` Method ✅
- [ ] Read `CONVERSATION_HISTORY` from scratchpad
- [ ] Include conversation context in prompt
- [ ] Format conversation history for LLM consumption
- [ ] Pass problem description AND conversation history

### Phase 3: Remove Custom Parameter Extraction Logic ✅
- [ ] Review `_fetch_kubernetes()` and `_fetch_prometheus()` methods
- [ ] Identify any hardcoded parameter extraction logic
- [ ] Remove custom logic that should be delegated to LLM
- [ ] Ensure methods only pass through explicitly provided parameters

### Phase 4: Update SK Prompt Building ✅
- [ ] Update `_build_sk_prompt()` to use conversational templates
- [ ] Include instructions for LLM to ask clarifying questions
- [ ] Add examples of parameter extraction from conversation
- [ ] Ensure prompt clearly indicates plugin availability

### Phase 5: Update Unit Tests ⏳
- [ ] Add tests for conversation history inclusion in prompts
- [ ] Add tests for LLM receiving conversation context
- [ ] Add tests for plugin invocation with conversational parameters
- [ ] Add tests for clarifying question generation
- [ ] Ensure no tests assume custom extraction logic

### Phase 6: Integration Testing ⏳
- [ ] Test with mocked conversation history
- [ ] Test with missing parameters (should trigger clarification)
- [ ] Test with complete conversation context
- [ ] Verify plugins are called correctly

---

## Changes Made

### Files Modified
1. `aletheia/llm/prompts.py` - Added conversational prompt templates
2. `aletheia/agents/data_fetcher.py` - Updated `_build_sk_prompt()` method
3. `tests/unit/test_data_fetcher_agent.py` - Updated tests for conversational mode

---

## Notes

- The Data Fetcher already uses SK with plugins (implemented in task 3.4.8)
- Current implementation has some direct parameter handling that should be LLM-delegated
- Need to ensure conversation history is properly read from scratchpad
- Plugin functions are already defined and registered
- Focus on enhancing prompts and removing custom extraction logic

---

## Testing Strategy

1. **Unit Tests**: Mock conversation history and verify LLM prompt includes it
2. **Plugin Tests**: Verify plugins are invoked with parameters extracted by LLM
3. **Clarification Tests**: Verify LLM generates questions when parameters missing
4. **Integration Tests**: Test full conversational flow with mocked LLM responses

---

## Session Progress

**Start Time**: 2025-10-17
**Current Phase**: Phase 1 - Adding conversational prompt templates
