# Aletheia (ἀλήθεια)

> **Aletheia** (ἀλήθεια) — Ancient Greek for "truth" or "un-concealment": bringing what's hidden into the open.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Aletheia is a modular, AI-powered troubleshooting framework for SREs and system administrators. It orchestrates specialized LLM agents to collect observability data (logs, metrics, traces), analyze patterns, inspect code, and generate actionable root cause hypotheses.

---

## 🌟 Key Features

- **Multi-Agent Orchestration:** Modular agents for data collection, pattern analysis, and root cause reasoning.
- **Pluggable Data Fetchers:** Integrates with Kubernetes, Prometheus, log files, and more.
- **LLM-Driven Reasoning:** Uses prompt templates and plugins for advanced, context-aware analysis.
- **Extensible Plugins:** Add new data sources or tools via Semantic Kernel plugins.
- **Conversational Mode:** Natural language troubleshooting with full conversation context.
- **CLI & Automation:** Command-line interface for interactive or automated sessions.

---

## 🗂️ Project Structure

```
aletheia/
├── agents/         # AI agent implementations and orchestration logic
├── demo/           # Demo scenarios and example orchestrators
├── fetchers/       # Data fetcher modules for various sources (K8s, Prometheus, etc.)
├── llm/            # LLM service integration and prompt templates
├── plugins/        # Semantic Kernel plugins for external tools/APIs
├── utils/          # Utility modules (logging, validation, etc.)
├── banner.txt      # CLI banner
├── cli.py          # Command-line interface entrypoint
├── config.py       # Configuration loading and management
├── encryption.py   # Encryption utilities
├── scratchpad.py   # Shared state and memory for agents
├── session.py      # Session management
```

---

## 🚀 Getting Started

1. **Install dependencies:**
	```bash
	pip install -r requirements.txt -r requirements-dev.txt
	# or use uv for faster installs
	uv pip install -r requirements.txt -r requirements-dev.txt
	```

2. **Run the CLI:**
	```bash
	python -m aletheia.cli session open
	```

3. **Configure agents and plugins:**
	- Edit your configuration YAML to specify LLM settings, agent routing, and data source credentials.

4. **Extend functionality:**
	- Add new agents in `aletheia/agents/`
	- Implement new plugins in `aletheia/plugins/`
	- Add prompt templates in `aletheia/llm/prompts/`

---

## 🧩 Extending Aletheia

- **Add a Data Fetcher:**
  1. Create a fetcher in `aletheia/fetchers/`.
  2. Implement a plugin in `aletheia/plugins/` with `@kernel_function` decorators.
  3. Register the plugin in your agent's `__init__`.
  4. Add a prompt template in `aletheia/llm/prompts/`.
  5. Update orchestration logic if needed.

- **Add an Agent:**
  - Inherit from `SKBaseAgent` in `aletheia/agents/sk_base.py`.
  - Register required plugins.
  - Implement the `execute()` method.

---

## 🧪 Testing

- Unit tests are in the `tests/` directory.
- Use `pytest` to run tests:
  ```bash
  pytest
  ```
- Aim for >80% code coverage.

---

## 🛠️ Development Guidelines

- Follow PEP 8 and use type hints.
- Write docstrings for all public classes and functions.
- Keep code modular and focused.
- See `AGENTS.md` and `SPECIFICATION.md` for detailed patterns and architecture.

---

## 📚 Documentation

- [AGENTS.md](AGENTS.md): Agent and plugin development guide
- [SPECIFICATION.md](SPECIFICATION.md): Product requirements and architecture
- [MIGRATION_SK.md](MIGRATION_SK.md): Semantic Kernel migration guide

---

## 🤝 Contributing

Pull requests are welcome! Please follow the code style and contribution guidelines.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
