## Session Update - 2025-10-17 (Intent-Based Orchestration Implementation)

### Task: REFACTOR-1 - Intent-Based Orchestration

**Status**: 🚧 IN PROGRESS

**Worktree**: `worktrees/feat/ref-1-intent-based-orchestration`
**Branch**: `feat/ref-1-intent-based-orchestration`
**Started**: 2025-10-17

#### Task Requirements (from TODO.md):

**REFACTOR-1**: Implement intent-based orchestration
- [ ] Add `_execute_conversational_mode()` to OrchestratorAgent
- [ ] Implement `_understand_user_intent()` with LLM intent parsing
- [ ] Implement `_decide_next_agent()` for dynamic routing
- [ ] Add conversation history tracking in scratchpad
- **Acceptance**: Orchestrator can route based on user intent, not just phases

#### Implementation Plan:

1. **Add Conversational Mode to Orchestrator**:
   - Create `_execute_conversational_mode()` method
   - Implement conversation loop with user input
   - Store conversation history in scratchpad

2. **Intent Understanding**:
   - Create `_understand_user_intent()` method
   - Use LLM (via SK or custom provider) to parse user natural language
   - Extract intents like:
     - "fetch_data" (user wants data collection)
     - "analyze_patterns" (user wants pattern analysis)
     - "inspect_code" (user wants code inspection)
     - "diagnose" (user wants root cause analysis)
     - "show_findings" (user wants to see results)
     - "clarify" (user is asking questions/clarifying)

3. **Dynamic Routing**:
   - Create `_decide_next_agent()` method
   - Map intents to appropriate specialist agents
   - Handle sequential dependencies (e.g., can't analyze patterns without data)

4. **Conversation History**:
   - Add `CONVERSATION_HISTORY` section to scratchpad
   - Track user messages and assistant responses
   - Provide context for intent understanding

#### Current Understanding:

From SPECIFICATION.md:
- Conversational mode uses natural language interaction
- LLM-powered intent understanding
- More flexible but potentially slower than guided mode
- Example: "Show me errors from payments service in the last 2 hours"
  → Aletheia understands intent and routes to data fetcher

#### Architecture Notes:

- Orchestrator already has phase-based routing (_execute_guided_mode)
- Need to add parallel conversational routing
- Use existing agent_registry for routing
- Leverage SK ChatCompletionAgent if available, or fallback to custom LLM provider

#### Next Steps:

1. Define intent schema/enum
2. Implement `_understand_user_intent()` with LLM prompt
3. Implement `_execute_conversational_mode()` conversation loop
4. Add conversation history to scratchpad schema
5. Implement `_decide_next_agent()` routing logic
6. Add unit tests for intent understanding and routing
7. Update TODO.md to mark REFACTOR-1 as complete

#### Dependencies:

- `aletheia/agents/orchestrator.py` (main implementation file)
- `aletheia/scratchpad.py` (add CONVERSATION_HISTORY section)
- `aletheia/llm/prompts.py` (add intent understanding prompts)
- Existing SK/LLM infrastructure

#### Testing Strategy:

- Mock LLM responses for different intents
- Test routing logic with different intent sequences
- Test conversation history tracking
- Test edge cases (unclear intent, missing data dependencies)
