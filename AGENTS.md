# Aletheia (ἀλήθεια)

> **Aletheia** (ἀλήθεια) — Ancient Greek for "truth" or "un-concealment": bringing what's hidden into the open.

Aletheia is a modular, AI-powered troubleshooting framework for SREs and system administrators. It orchestrates specialized LLM agents to collect and analyze observability data (logs, metrics, traces), inspect code, and generate actionable root cause hypotheses.

---

# Python Project Guidelines

When developing agents or contributing to Aletheia, please adhere to the following guidelines to ensure code quality and consistency.

## 1. Environment Management

Aletheia uses **[uv](https://github.com/astral-sh/uv)** for fast Python package management.

*   **Create Virtual Environment**: `uv venv --python python3.12`
*   **Install Dependencies**: `uv pip install -r requirements.txt`
*   **Install Dev Dependencies**: `uv pip install -r requirements-dev.txt`

## 2. Code Style & Formatting

We enforce a consistent code style using **Black** and **Ruff**.

*   **Formatter**: [Black](https://github.com/psf/black)
    *   Line length: 88 characters
    *   Target versions: py310, py311, py312
*   **Linter**: [Ruff](https://github.com/astral-sh/ruff)
    *   Used for import sorting (isort), pyflakes, pycodestyle, and more.
    *   Configuration is in `pyproject.toml`.

**Command to format code:**
```bash
black .
ruff check --fix .
```

## 3. Type Safety

All new code must be fully typed. We use **mypy** for static type checking.

*   **Strict Mode**: Enabled.
*   **Disallow Untyped Defs**: Enabled.

**Command to check types:**
```bash
mypy .
```

## 4. Testing

We use **pytest** for testing.

*   **Async Support**: `pytest-asyncio` is used for async tests.
*   **Coverage**: `pytest-cov` is configured to track coverage.

**Command to run tests:**
```bash
pytest
```

## 5. Development Workflow

Before submitting a Pull Request, ensure you have run the following:

1.  Format code: `black .`
2.  Lint code: `ruff check .`
3.  Check types: `mypy .`
4.  Run tests: `pytest`


## 6. Frameworks
Use the following frameworks:
- FastAPI for APIs
- Tailwind CSS for csso

# IMPORTANT
- ALWAYS activate the virtual environment before running the agent
- ALWAYS keep the code simple and readable. DO NOT overengineer
