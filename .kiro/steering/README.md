# Aletheia Steering Documents

This directory contains comprehensive development guides for the Aletheia project. These documents provide detailed guidance on architecture, development practices, testing, security, and contribution guidelines.

## Document Overview

### [00-quick-reference.md](00-quick-reference.md)
**Quick Reference Guide** - Essential commands, patterns, and troubleshooting tips for daily development.

**Use when**: You need a quick lookup for common commands, patterns, or fixes.

**Key sections**:
- Essential commands (setup, testing, CLI)
- Common code patterns
- Quick troubleshooting fixes
- Configuration snippets

---

### [01-architecture.md](01-architecture.md)
**Architecture Overview** - High-level system design and component relationships.

**Use when**: Understanding the overall system structure, planning new features, or onboarding.

**Key sections**:
- Agent-based system architecture
- Core components and their responsibilities
- Data flow through the system
- Extension points for customization

---

### [02-development-workflow.md](02-development-workflow.md)
**Development Workflow** - Day-to-day development practices and tooling.

**Use when**: Setting up your environment, running quality checks, or following development best practices.

**Key sections**:
- Environment setup with uv
- Pre-commit checklist
- Code quality standards (Black, Ruff, mypy)
- Testing workflow
- Git workflow and commit conventions

---

### [03-agent-development.md](03-agent-development.md)
**Agent Development Guide** - Creating and extending agents and plugins.

**Use when**: Building new agents, adding plugins, or implementing skills.

**Key sections**:
- Agent architecture and lifecycle
- Creating new agents and plugins
- Tool design best practices
- Skills system for complex orchestrations
- Agent testing patterns

---

### [04-configuration-management.md](04-configuration-management.md)
**Configuration Management** - Configuration system, options, and credential management.

**Use when**: Configuring Aletheia, managing credentials, or setting up different environments.

**Key sections**:
- Configuration hierarchy (env vars, YAML, defaults)
- LLM provider configuration
- Credential storage options
- Per-agent configuration
- MCP server configuration

---

### [05-security-and-encryption.md](05-security-and-encryption.md)
**Security and Encryption** - Security practices, encryption, and credential management.

**Use when**: Handling sensitive data, implementing security features, or reviewing security practices.

**Key sections**:
- Session encryption (AES-256-GCM)
- Credential storage types
- Secrets management best practices
- Input validation and injection prevention
- Security checklist and incident response

---

### [06-testing-strategy.md](06-testing-strategy.md)
**Testing Strategy** - Comprehensive testing approach and best practices.

**Use when**: Writing tests, improving coverage, or setting up CI/CD.

**Key sections**:
- Test organization and structure
- Unit, integration, and E2E testing
- Mocking external dependencies
- Async testing patterns
- Coverage goals and CI setup

---

### [07-troubleshooting-guide.md](07-troubleshooting-guide.md)
**Troubleshooting Guide** - Common issues, solutions, and debugging techniques.

**Use when**: Encountering errors, debugging issues, or helping others troubleshoot.

**Key sections**:
- Environment and setup issues
- Configuration problems
- LLM provider issues
- Agent and plugin errors
- Debugging techniques

---

### [08-contributing-guide.md](08-contributing-guide.md)
**Contributing Guide** - How to contribute to the project.

**Use when**: Contributing code, documentation, or tests to the project.

**Key sections**:
- Fork and setup workflow
- Pull request guidelines
- Code review process
- Adding new components
- Community guidelines

---

## How to Use These Documents

### For New Contributors

1. Start with **00-quick-reference.md** for essential commands
2. Read **01-architecture.md** to understand the system
3. Follow **02-development-workflow.md** to set up your environment
4. Review **08-contributing-guide.md** before making contributions

### For Feature Development

1. Review **01-architecture.md** for system design
2. Follow **03-agent-development.md** for agents/plugins
3. Use **06-testing-strategy.md** for testing
4. Check **02-development-workflow.md** for quality checks

### For Configuration

1. Start with **04-configuration-management.md**
2. Check **05-security-and-encryption.md** for credentials
3. Use **00-quick-reference.md** for quick lookups

### For Troubleshooting

1. Check **00-quick-reference.md** for quick fixes
2. Review **07-troubleshooting-guide.md** for detailed solutions
3. Enable verbose logging: `aletheia session open -vv`

## Document Maintenance

These steering documents should be updated when:

- New features are added
- Architecture changes
- Best practices evolve
- Common issues are discovered
- Configuration options change

## Quick Links

- **Project README**: `../README.md`
- **Agent Guide**: `../AGENTS.md`
- **Example Config**: `../config.yaml.example`
- **Tests**: `../tests/`

## Getting Help

If these documents don't answer your question:

1. Search existing GitHub issues
2. Check the test suite for examples
3. Ask in GitHub Discussions
4. Open a new issue with details

## Contributing to Documentation

Documentation improvements are always welcome! To contribute:

1. Follow the same workflow as code contributions
2. Use clear, concise language
3. Include code examples where helpful
4. Test all commands and code snippets
5. Update this README if adding new documents

## Document Format

All steering documents follow this format:

```markdown
---
inclusion: always
---

# Document Title

## Section 1
Content...

## Section 2
Content...
```

The frontmatter `inclusion: always` ensures these documents are always included in Kiro's context when working on this project.

---

**Last Updated**: January 2026

**Maintained By**: Aletheia Contributors

**Questions?** Open an issue on GitHub
