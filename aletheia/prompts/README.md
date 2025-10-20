# Aletheia Prompt Templates

This directory contains all prompt templates used by Aletheia's specialist agents. Externalizing prompts to files allows for easier iteration, customization, and version control without code changes.

## Directory Structure

```
prompts/
├── README.md                                   # This file
├── triage_agent_instructions.md                # Triage agent SK instructions
├── data_fetcher_system.md                      # Data fetcher system prompt (guided)
├── data_fetcher_conversational_system.md       # Data fetcher system prompt (conversational)
├── data_fetcher_conversational.md              # Data fetcher user prompt template
├── pattern_analyzer_system.md                  # Pattern analyzer system prompt (guided)
├── pattern_analyzer_conversational_system.md   # Pattern analyzer system prompt (conversational)
├── pattern_analyzer_conversational.md          # Pattern analyzer user prompt template
├── code_inspector_system.md                    # Code inspector system prompt (guided)
├── code_inspector_conversational_system.md     # Code inspector system prompt (conversational)
├── code_inspector_conversational.md            # Code inspector user prompt template
├── root_cause_analyst_system.md                # Root cause analyst system prompt (guided)
├── root_cause_analyst_conversational_system.md # Root cause analyst system prompt (conversational)
├── root_cause_analyst_conversational.md        # Root cause analyst user prompt template
├── orchestrator_system.md                      # Orchestrator system prompt
├── intent_understanding_system.md              # Intent understanding system prompt
├── intent_understanding.md                     # Intent understanding user prompt template
├── agent_routing_system.md                     # Agent routing system prompt
└── agent_routing_decision.md                   # Agent routing decision user prompt template
```

## Template Naming Convention

Templates follow a consistent naming pattern:

- **System Prompts** (define agent role and capabilities):
  - `<agent_name>_system.md` - Guided mode system prompt
  - `<agent_name>_conversational_system.md` - Conversational mode system prompt
  - `<agent_name>_instructions.md` - SK agent instructions (for SK ChatCompletionAgent)

- **User Prompts** (define specific tasks with variable placeholders):
  - `<agent_name>_<operation>.md` - Operation-specific user prompt template
  - `<agent_name>_conversational.md` - Conversational mode user prompt template

## Variable Substitution

User prompt templates support variable substitution using `{variable_name}` syntax. For example:

```markdown
=== PROBLEM CONTEXT ===
{problem_description}

=== CONVERSATION HISTORY ===
{conversation_history}
```

Common variables:
- `{problem_description}` - User's problem description
- `{conversation_history}` - Full conversation history
- `{collected_data}` - Data collected by data fetcher
- `{pattern_analysis}` - Pattern analysis results
- `{code_inspection}` - Code inspection results
- `{agent_notes}` - Notes from other agents
- `{investigation_state}` - Current investigation state
- `{data_sources}` - Available data sources

## Customization

### For Development
Prompts can be edited directly in this directory. Changes take effect immediately after reloading the `PromptTemplateLoader`.

### For Users
Users can customize prompts by:
1. Copying this directory to a custom location
2. Editing the templates as needed
3. Setting `llm.prompt_templates_dir` in configuration to point to the custom directory

Example configuration:
```yaml
llm:
  prompt_templates_dir: "/path/to/custom/prompts/"
```

If a template is not found in the custom directory, the loader falls back to built-in templates.

## Template Guidelines

When creating or editing templates:

1. **Be Specific**: Clearly define the agent's role, capabilities, and constraints
2. **Use Examples**: Include examples of expected input/output formats
3. **Define Variables**: Document all required variables in comments at the top
4. **Version Control**: Track changes to prompts just like code
5. **Test Thoroughly**: Test prompt changes with various scenarios before deployment
6. **LLM-First Design**: Delegate logic to LLM via clear instructions, not hardcoded rules

## Semantic Kernel Integration

Templates are loaded by the `PromptTemplateLoader` class in `aletheia/llm/prompts.py` and used by:

- **SK Agents**: Load system prompts/instructions during initialization
- **Prompt Building**: Load user prompt templates and substitute variables
- **Conversational Mode**: Load conversational-specific templates with context

## Maintenance

When adding a new agent or operation:

1. Create system prompt template (if new agent)
2. Create user prompt template (if new operation)
3. Follow naming convention
4. Update this README with the new template
5. Add tests in `tests/llm/test_prompt_templates.py`
6. Document variables used in the template

## See Also

- `aletheia/llm/prompts.py` - PromptTemplateLoader implementation
- `AGENTS.md` - Agent development guide with prompt engineering patterns
- `SPECIFICATION.md` - System architecture and agent descriptions
