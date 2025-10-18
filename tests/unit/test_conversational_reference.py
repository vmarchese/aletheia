"""Tests for Conversational Mode Reference Implementation.

These tests verify that the reference implementation correctly demonstrates
the LLM-First pattern without implementing actual logic. They serve as
documentation and validation of the conversational approach.
"""

import pytest
from aletheia.agents.workflows.conversational import (
    # Example functions
    orchestrator_understand_intent_example,
    orchestrator_decide_next_agent_example,
    data_fetcher_conversational_execution_example,
    generate_clarification_question_example,
    code_inspector_conversational_execution_example,
    conversational_flow_walkthrough,
    # Example prompts
    EXAMPLE_INTENT_UNDERSTANDING_PROMPT,
    EXAMPLE_AGENT_ROUTING_PROMPT,
    EXAMPLE_DATA_FETCHER_PROMPT,
    EXAMPLE_CLARIFICATION_PROMPT,
    EXAMPLE_CODE_INSPECTOR_PROMPT,
)


class TestOrchestratorIntentUnderstanding:
    """Tests for intent understanding pattern."""
    
    def test_intent_prompt_includes_conversation_history(self):
        """Verify prompt includes full conversation history."""
        conversation = "user: Why is payments-svc failing?"
        state = {"data_collected": False}
        
        prompt = orchestrator_understand_intent_example(conversation, state)
        
        assert conversation in prompt
        assert "conversation" in prompt.lower()
    
    def test_intent_prompt_includes_investigation_state(self):
        """Verify prompt includes current investigation state."""
        conversation = "user: Check the logs"
        state = {"data_collected": True, "agents_run": ["data_fetcher"]}
        
        prompt = orchestrator_understand_intent_example(conversation, state)
        
        # State should be in prompt (as str representation)
        assert "investigation_state" in prompt.lower() or str(state) in prompt
    
    def test_intent_prompt_lists_available_actions(self):
        """Verify prompt lists available actions for LLM."""
        conversation = "user: What's wrong?"
        state = {}
        
        prompt = orchestrator_understand_intent_example(conversation, state)
        
        # Should list key actions
        assert "collect_data" in prompt
        assert "analyze_patterns" in prompt
        assert "inspect_code" in prompt
        assert "diagnose_root_cause" in prompt
        assert "clarify" in prompt
    
    def test_intent_prompt_requests_json_response(self):
        """Verify prompt asks for structured JSON response."""
        conversation = "user: Investigate issue"
        state = {}
        
        prompt = orchestrator_understand_intent_example(conversation, state)
        
        assert "json" in prompt.lower() or "JSON" in prompt
        assert "intent" in prompt
        assert "confidence" in prompt
        assert "parameters" in prompt
    
    def test_intent_prompt_encourages_parameter_extraction(self):
        """Verify prompt guides LLM to extract parameters from conversation."""
        conversation = "user: Check payments-svc in production namespace"
        state = {}
        
        prompt = orchestrator_understand_intent_example(conversation, state)
        
        # Should guide extraction
        assert "extract" in prompt.lower() or "parameters" in prompt.lower()
        # Should provide examples
        assert "service" in prompt.lower() or "pod" in prompt.lower()


class TestOrchestratorAgentRouting:
    """Tests for agent routing pattern."""
    
    def test_routing_prompt_includes_all_context(self):
        """Verify routing prompt includes conversation, state, and intent."""
        conversation = "user: Investigate payments-svc"
        state = {"data_collected": False}
        intent = "collect_data"
        params = {"service": "payments-svc"}
        confidence = 0.9
        
        prompt = orchestrator_decide_next_agent_example(
            conversation, state, intent, params, confidence
        )
        
        assert conversation in prompt
        assert intent in prompt
        assert str(confidence) in prompt
    
    def test_routing_prompt_lists_all_agents(self):
        """Verify prompt describes all available specialist agents."""
        conversation = "user: Help"
        state = {}
        
        prompt = orchestrator_decide_next_agent_example(
            conversation, state, "investigate", {}, 0.8
        )
        
        # Should list all 4 specialist agents
        assert "data_fetcher" in prompt
        assert "pattern_analyzer" in prompt
        assert "code_inspector" in prompt
        assert "root_cause_analyst" in prompt
    
    def test_routing_prompt_describes_prerequisites(self):
        """Verify prompt explains prerequisites for each agent."""
        conversation = "user: Analyze patterns"
        state = {}
        
        prompt = orchestrator_decide_next_agent_example(
            conversation, state, "analyze_patterns", {}, 0.9
        )
        
        assert "prerequisites" in prompt.lower()
        # Pattern analyzer needs DATA_COLLECTED
        assert "DATA_COLLECTED" in prompt or "data collected" in prompt.lower()
    
    def test_routing_prompt_no_hardcoded_mappings(self):
        """Verify routing is LLM-driven, not hardcoded."""
        # The prompt itself should NOT contain hardcoded if/elif logic
        prompt = EXAMPLE_AGENT_ROUTING_PROMPT
        
        # Should ask LLM to decide, not provide mappings
        assert "decide" in prompt.lower() or "decision" in prompt.lower()
        assert "reasoning" in prompt.lower()
        
        # Should NOT contain Python-like conditionals
        assert "if intent ==" not in prompt
        assert "elif" not in prompt
    
    def test_routing_prompt_requests_structured_decision(self):
        """Verify prompt asks for structured routing decision."""
        conversation = "user: Check logs"
        state = {}
        
        prompt = orchestrator_decide_next_agent_example(
            conversation, state, "collect_data", {}, 0.95
        )
        
        assert "action" in prompt
        assert "agent" in prompt
        assert "reasoning" in prompt
        assert "prerequisites_met" in prompt


class TestDataFetcherConversational:
    """Tests for Data Fetcher conversational pattern."""
    
    def test_fetcher_prompt_includes_conversation(self):
        """Verify Data Fetcher prompt includes full conversation."""
        conversation = "user: Fetch logs from payments-svc in production"
        problem = {"description": "Service failing", "services": ["payments-svc"]}
        
        prompt = data_fetcher_conversational_execution_example(conversation, problem)
        
        assert conversation in prompt
    
    def test_fetcher_prompt_lists_available_plugins(self):
        """Verify prompt lists Kubernetes and Prometheus plugins."""
        conversation = "user: Get data"
        problem = {}
        
        prompt = data_fetcher_conversational_execution_example(conversation, problem)
        
        # Should list plugin functions
        assert "kubernetes" in prompt.lower()
        assert "prometheus" in prompt.lower()
        assert "fetch_kubernetes_logs" in prompt or "fetch" in prompt
        assert "fetch_prometheus_metrics" in prompt or "metrics" in prompt
    
    def test_fetcher_prompt_guides_parameter_extraction(self):
        """Verify prompt instructs LLM to extract parameters from conversation."""
        conversation = "user: Check payments pod in staging for last 2 hours"
        problem = {}
        
        prompt = data_fetcher_conversational_execution_example(conversation, problem)
        
        assert "extract" in prompt.lower() or "parameters" in prompt.lower()
        # Should guide on what to extract
        assert "pod" in prompt.lower() or "service" in prompt.lower()
        assert "namespace" in prompt.lower()
        assert "time" in prompt.lower() or "window" in prompt.lower()
    
    def test_fetcher_prompt_emphasizes_no_custom_extraction(self):
        """Verify prompt emphasizes LLM does extraction, not custom code."""
        conversation = "user: Investigate"
        problem = {}
        
        prompt = data_fetcher_conversational_execution_example(conversation, problem)
        
        # Should explicitly state not to write custom code
        assert "do not" in prompt.lower() or "don't" in prompt.lower()
        # Should mention automatic function calling
        assert "automatic" in prompt.lower() or "auto" in prompt.lower()
    
    def test_fetcher_prompt_requests_natural_language_summary(self):
        """Verify prompt asks for natural language summary of collected data."""
        conversation = "user: Get logs"
        problem = {}
        
        prompt = data_fetcher_conversational_execution_example(conversation, problem)
        
        assert "summar" in prompt.lower()  # "summary" or "summarize"


class TestClarificationQuestions:
    """Tests for clarification question generation pattern."""
    
    def test_clarification_prompt_includes_conversation(self):
        """Verify clarification prompt includes conversation history."""
        conversation = "user: Check the service\nagent: Which service?"
        missing = "service_name"
        
        prompt = generate_clarification_question_example(conversation, missing)
        
        assert conversation in prompt
    
    def test_clarification_prompt_specifies_missing_info(self):
        """Verify prompt specifies what information is needed."""
        conversation = "user: Investigate the issue"
        missing = "namespace"
        
        prompt = generate_clarification_question_example(conversation, missing)
        
        assert missing in prompt
    
    def test_clarification_prompt_requests_natural_question(self):
        """Verify prompt asks LLM to generate natural, helpful question."""
        conversation = "user: Help"
        missing = "pod_name"
        
        prompt = generate_clarification_question_example(conversation, missing)
        
        assert "question" in prompt.lower()
        assert "natural" in prompt.lower() or "conversational" in prompt.lower()
    
    def test_clarification_prompt_encourages_examples(self):
        """Verify prompt encourages providing examples in questions."""
        conversation = "user: Check logs"
        missing = "namespace"
        
        prompt = generate_clarification_question_example(conversation, missing)
        
        assert "example" in prompt.lower()


class TestCodeInspectorConversational:
    """Tests for Code Inspector conversational pattern."""
    
    def test_inspector_prompt_includes_conversation(self):
        """Verify Code Inspector prompt includes conversation."""
        conversation = "user: The code at features.go:57 is failing"
        analysis = {"stack_traces": ["features.go:57"]}
        
        prompt = code_inspector_conversational_execution_example(conversation, analysis)
        
        assert conversation in prompt
    
    def test_inspector_prompt_includes_pattern_analysis(self):
        """Verify prompt includes pattern analysis with stack traces."""
        conversation = "user: Investigate"
        analysis = {
            "stack_traces": ["features.go:57", "promo.go:88"],
            "error_clusters": {"nil pointer": 45}
        }
        
        prompt = code_inspector_conversational_execution_example(conversation, analysis)
        
        # Analysis should be in prompt
        assert "pattern" in prompt.lower() or str(analysis) in prompt
    
    def test_inspector_prompt_lists_git_plugins(self):
        """Verify prompt lists available git plugin functions."""
        conversation = "user: Check the code"
        analysis = {}
        
        prompt = code_inspector_conversational_execution_example(conversation, analysis)
        
        assert "git" in prompt.lower()
        assert "find_file" in prompt.lower() or "find_file_in_repo" in prompt
        assert "blame" in prompt.lower() or "git_blame" in prompt
        assert "extract_code" in prompt.lower() or "extract_code_context" in prompt
    
    def test_inspector_prompt_guides_repo_extraction(self):
        """Verify prompt guides LLM to extract repository info from conversation."""
        conversation = "user: The repo is at git@company:platform/featurekit.git"
        analysis = {}
        
        prompt = code_inspector_conversational_execution_example(conversation, analysis)
        
        assert "repository" in prompt.lower() or "repo" in prompt.lower()
        assert "extract" in prompt.lower() or "mentioned" in prompt.lower()
    
    def test_inspector_prompt_handles_missing_repos(self):
        """Verify prompt instructs LLM to ask for repos if not provided."""
        conversation = "user: Check the code"
        analysis = {"stack_traces": ["features.go:57"]}
        
        prompt = code_inspector_conversational_execution_example(conversation, analysis)
        
        # Should mention asking for repository paths if missing
        assert "ask" in prompt.lower() or "need" in prompt.lower()


class TestConversationalFlowWalkthrough:
    """Tests for complete conversational flow example."""
    
    def test_walkthrough_executes_without_errors(self):
        """Verify walkthrough function runs without errors."""
        # This is pseudocode, but should not raise exceptions
        conversational_flow_walkthrough()
    
    def test_walkthrough_is_well_documented(self):
        """Verify walkthrough function has comprehensive documentation."""
        import inspect
        doc = inspect.getdoc(conversational_flow_walkthrough)
        
        assert doc is not None
        assert len(doc) > 100  # Should have substantial documentation
        assert "step" in doc.lower() or "example" in doc.lower()


class TestPromptTemplates:
    """Tests for example prompt templates."""
    
    def test_intent_prompt_template_is_comprehensive(self):
        """Verify intent understanding prompt template is comprehensive."""
        prompt = EXAMPLE_INTENT_UNDERSTANDING_PROMPT
        
        assert len(prompt) > 200  # Should be substantial
        assert "{conversation_history}" in prompt
        assert "{investigation_state}" in prompt
        assert "intent" in prompt.lower()
    
    def test_routing_prompt_template_is_comprehensive(self):
        """Verify routing prompt template is comprehensive."""
        prompt = EXAMPLE_AGENT_ROUTING_PROMPT
        
        assert len(prompt) > 300
        assert "{conversation_history}" in prompt
        assert "{intent}" in prompt
        assert "agent" in prompt.lower()
    
    def test_fetcher_prompt_template_is_comprehensive(self):
        """Verify data fetcher prompt template is comprehensive."""
        prompt = EXAMPLE_DATA_FETCHER_PROMPT
        
        assert len(prompt) > 300
        assert "{conversation_history}" in prompt
        assert "plugin" in prompt.lower()
        assert "kubernetes" in prompt.lower()
    
    def test_clarification_prompt_template_is_comprehensive(self):
        """Verify clarification prompt template is comprehensive."""
        prompt = EXAMPLE_CLARIFICATION_PROMPT
        
        assert len(prompt) > 100
        assert "{conversation_history}" in prompt
        assert "{missing_information}" in prompt
        assert "question" in prompt.lower()
    
    def test_inspector_prompt_template_is_comprehensive(self):
        """Verify code inspector prompt template is comprehensive."""
        prompt = EXAMPLE_CODE_INSPECTOR_PROMPT
        
        assert len(prompt) > 300
        assert "{conversation_history}" in prompt
        assert "{pattern_analysis}" in prompt
        assert "git" in prompt.lower()


class TestLLMFirstPrinciples:
    """Tests verifying adherence to LLM-First principles."""
    
    def test_no_regex_in_reference_code(self):
        """Verify reference implementation doesn't use regex for extraction."""
        import inspect
        from aletheia.agents.workflows import conversational
        
        source = inspect.getsource(conversational)
        
        # Should not import re module at top level
        assert "import re\n" not in source
        assert "from re import" not in source
        
        # Should mention regex only in anti-pattern examples (marked with ❌)
        # Count occurrences of re.search - should be in BAD example only
        re_search_count = source.count("re.search")
        # If it appears, it should be in a comment or marked as wrong
        if re_search_count > 0:
            # Find the context around re.search
            lines = source.split('\n')
            for i, line in enumerate(lines):
                if 're.search' in line:
                    # Should be in a comment or near a "WRONG" marker
                    context = '\n'.join(lines[max(0, i-5):i+5])
                    assert ('❌' in context or 'WRONG' in context or 
                            '# ' in line or 'BAD' in context), \
                            f"re.search found outside anti-pattern example at line {i}"
    
    def test_no_hardcoded_intent_mappings(self):
        """Verify no hardcoded intent-to-agent mappings in reference."""
        import inspect
        from aletheia.agents.workflows import conversational
        
        source = inspect.getsource(conversational)
        
        # Should not have dictionary mappings like intent_to_agent
        assert "intent_to_agent" not in source
        assert 'if intent == "' not in source
        assert 'elif intent == "' not in source
    
    def test_no_subprocess_calls(self):
        """Verify reference doesn't make direct subprocess calls."""
        import inspect
        from aletheia.agents.workflows import conversational
        
        source = inspect.getsource(conversational)
        
        # Should not import subprocess at top level
        assert "import subprocess\n" not in source
        assert "from subprocess import" not in source
        
        # Should mention subprocess only in anti-pattern examples (marked with ❌)
        subprocess_count = source.count("subprocess.run")
        if subprocess_count > 0:
            # Find the context around subprocess.run
            lines = source.split('\n')
            for i, line in enumerate(lines):
                if 'subprocess.run' in line:
                    # Should be in a comment or near a "WRONG" marker
                    context = '\n'.join(lines[max(0, i-5):i+5])
                    assert ('❌' in context or 'WRONG' in context or 
                            '# ' in line or 'BAD' in context), \
                            f"subprocess.run found outside anti-pattern example at line {i}"
    
    def test_emphasizes_plugin_usage(self):
        """Verify reference emphasizes using plugins, not direct calls."""
        import inspect
        from aletheia.agents.workflows import conversational
        
        source = inspect.getsource(conversational)
        
        # Should mention plugins frequently
        assert source.count("plugin") > 10
        assert "FunctionChoiceBehavior" in source or "function" in source.lower()
    
    def test_module_docstring_explains_principles(self):
        """Verify module docstring explains LLM-First principles."""
        from aletheia.agents.workflows import conversational
        
        doc = conversational.__doc__
        
        assert doc is not None
        assert "LLM-First" in doc or "llm" in doc.lower()
        assert "delegate" in doc.lower()
        assert "plugin" in doc.lower()


class TestDocumentationQuality:
    """Tests for documentation quality in reference implementation."""
    
    def test_all_functions_have_docstrings(self):
        """Verify all example functions have comprehensive docstrings."""
        functions = [
            orchestrator_understand_intent_example,
            orchestrator_decide_next_agent_example,
            data_fetcher_conversational_execution_example,
            generate_clarification_question_example,
            code_inspector_conversational_execution_example,
            conversational_flow_walkthrough,
        ]
        
        for func in functions:
            assert func.__doc__ is not None
            assert len(func.__doc__) > 100  # Should be substantial
    
    def test_key_takeaways_section_exists(self):
        """Verify module has key takeaways section for developers."""
        import inspect
        from aletheia.agents.workflows import conversational
        
        source = inspect.getsource(conversational)
        
        assert "KEY TAKEAWAYS" in source or "key takeaway" in source.lower()
        assert "DO:" in source or "DON'T:" in source
    
    def test_examples_show_good_and_bad_patterns(self):
        """Verify documentation includes both good and bad examples."""
        import inspect
        from aletheia.agents.workflows import conversational
        
        source = inspect.getsource(conversational)
        
        # Should show both patterns
        assert "✅" in source or "GOOD" in source
        assert "❌" in source or "BAD" in source or "WRONG" in source
    
    def test_module_explains_what_not_to_do(self):
        """Verify module clearly explains anti-patterns."""
        from aletheia.agents.workflows import conversational
        
        doc = conversational.__doc__
        
        assert "DOES NOT" in doc or "don't" in doc.lower()
        assert "❌" in doc or "not" in doc.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
