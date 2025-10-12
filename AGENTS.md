# AGENTS.md - Python Development Guide

## Overview

This document provides guidelines for AI agents working on this Python project. Follow these instructions to ensure consistent development practices and maintain code quality.

## Prerequisites

- Python 3.8+
- [uv](https://github.com/astral-sh/uv) package manager
- Git with worktree support

## Package Management

This project uses **uv** as the package manager. All dependency management should be done through uv.

### Common uv Commands

```bash
# Install dependencies
uv pip install -r requirements.txt

# Install package in editable mode
uv pip install -e .

# Add a new dependency
uv pip install <package-name>

# Sync dependencies
uv pip sync requirements.txt
```

## Session Workflow

### 1. Start of Session - Feature Branch Setup

At the beginning of every development session, you **MUST**:
- Read thouroughlly the file SPECIFICATION.md
- Read the TODO.md file and .claude/memory.md file to check what is still missing
- Create a new worktree and branch:
  1. **Ask the user for the feature name:**
   ```
   "What feature would you like to work on? Please provide a short feature name (e.g., 'user-auth', 'api-endpoint', 'bug-fix-123')"
   ```
  2. **Create the worktree and branch:**
   ```bash
   git worktree add worktrees/feat/<feat-name> -b feat/<feat-name>
   ```

  3. **Navigate to the worktree:**
   ```bash
   cd worktrees/feat/<feat-name>
   ```

  4. **Set up the environment:**
   ```bash
   # Install dependencies
   uv pip install -r requirements.txt
   
   # Install development dependencies if they exist
   uv pip install -r requirements-dev.txt  # if applicable
   ```

### 2. Development Phase

- Make changes in the worktree directory
- Follow Python best practices (PEP 8, type hints, docstrings)
- Write tests for new functionality
- Commit changes regularly with clear, descriptive messages

```bash
git add .
git commit -m "feat: descriptive message about the change"
```

### 3. End of Session - Testing & Validation

Before considering the session complete, you **MUST**:

1. **Run all tests in the repository:**
   ```bash
   # Common test commands (adjust based on project setup)
   
   # If using pytest
   pytest
   
   # If using unittest
   python -m unittest discover
   
   # If using tox
   tox
   
   # With coverage
   pytest --cov=. --cov-report=term-missing
   ```

2. **Verify all tests pass:**
   - All tests must pass before finishing the session
   - If tests fail, fix the issues before concluding
   - Document any known issues or test failures

3. **Summary before finishing:**
   - Provide a summary of changes made
   - Confirm all tests passed
   - Note the branch name and worktree location

## Git Worktree Management

### Listing Worktrees
```bash
git worktree list
```

### Removing a Worktree (after merging)
```bash
# Remove the worktree
git worktree remove worktrees/feat/<feat-name>

# Delete the branch (if merged)
git branch -d feat/<feat-name>
```

### Switching Between Worktrees
Navigate to different worktrees using standard `cd` commands:
```bash
cd worktrees/feat/<different-feat-name>
```

## Code Quality Standards

### Style Guide
- Follow PEP 8 style guidelines
- Use meaningful variable and function names
- Maximum line length: 88 characters (Black formatter default)

### Type Hints
- Use type hints for function parameters and return values
- Use `typing` module for complex types

```python
from typing import List, Dict, Optional

def process_data(items: List[str], config: Dict[str, any]) -> Optional[str]:
    """Process data with given configuration."""
    pass
```

### Documentation
- Write docstrings for all public functions, classes, and modules
- Use Google or NumPy docstring format consistently
- Include examples in docstrings where helpful

### Testing
- Write unit tests for all new functionality
- Aim for >80% code coverage
- Use fixtures for common test setup
- Test edge cases and error conditions

## Project Structure

```
project/
├── src/                  # Source code
├── tests/                # Test files
├── worktrees/            # Git worktrees
│   └── feat/             # Feature worktrees
├── requirements.txt      # Production dependencies
├── requirements-dev.txt  # Development dependencies
├── pyproject.toml        # Project configuration
└── AGENTS.md            # This file
```

## Common Issues & Solutions

### Issue: uv command not found
**Solution:** Install uv using:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Issue: Worktree already exists
**Solution:** Remove existing worktree first:
```bash
git worktree remove worktrees/feat/<feat-name>
```

### Issue: Tests failing in worktree
**Solution:** Ensure dependencies are installed in the worktree:
```bash
cd worktrees/feat/<feat-name>
uv pip install -r requirements.txt -r requirements-dev.txt
```

## Session Checklist

- [ ] Asked user for feature name
- [ ] Created worktree: `worktrees/feat/<feat-name>`
- [ ] Created branch: `feat/<feat-name>`
- [ ] Installed dependencies with uv
- [ ] Implemented feature/fix
- [ ] Written/updated tests
- [ ] Committed changes with clear messages
- [ ] Ran all tests successfully
- [ ] All tests passing
- [ ] Provided session summary

## Notes

- Always work in the worktree, never in the main working directory during feature development
- Keep commits atomic and well-described
- If a session is interrupted, note the worktree location for continuation
- Clean up worktrees after features are merged to main

---

**Remember:** The mandatory steps are:
1. **Start:** Ask for feature name and create worktree
2. **End:** Run all tests and verify they pass