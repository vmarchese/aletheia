# Aletheia (ἀλήθεια)

> **Aletheia** (ἀλήθεια) — Ancient Greek for "truth" or "un-concealment": bringing what's hidden into the open.

Aletheia is a modular, AI-powered troubleshooting framework for SREs and system administrators. It orchestrates specialized LLM agents to collect and analyze observability data (logs, metrics, traces), inspect code, and generate actionable root cause hypotheses.

---

## Overview

Aletheia provides an interactive, agent-based workflow for troubleshooting distributed systems. It leverages Large Language Models (LLMs) and specialized plugins to automate data collection, pattern analysis, and root cause investigation across Kubernetes, Prometheus, log files, and more. The CLI offers a conversational interface for managing troubleshooting sessions, running investigations, and exploring demo scenarios.

## Installation

Aletheia requires Python 3.12 and uses [uv](https://github.com/astral-sh/uv) for dependency management.

### 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone the repository

```bash
git clone https://github.com/your-org/aletheia.git
cd aletheia
```

### 3. Create venv and install dependencies

```bash
uv venv --python python3.12
source ./.venv/bin/activate
uv pip install -r requirements.txt
uv pip install -r requirements-dev.txt  # for development
```

### 4. (Optional) Install in editable mode

```bash
uv pip install -e .
```

## Usage

Aletheia provides a command-line interface for managing troubleshooting sessions and running investigations.

### Command Line Interface

Run the CLI:

```bash
aletheia --help
```

#### Session Management

- **Open a new session:**

  ```bash
  aletheia session open
  ```

  Options:
  - `--name, -n`: Session name
  - `--verbose, -v`: Show all external commands and their output
  - `--very-verbose, -vv`: Enable trace logging with prompts, commands, and full details
  - `--unsafe`: Use plaintext storage (not recommended)

- **List sessions:**

  ```bash
  aletheia session list
  ```


- **Delete a session:**

  ```bash
  aletheia session delete <session_id>
  ```

- **Export a session:**


  ```bash
  aletheia session export <session_id> --output <file>
  ```

- **View session:**

  ```bash
  aletheia session view <session_id> 
  ```

- **View session timeline:**

  ```bash
  aletheia session timeline <session_id> 
  ```  


#### Version

```bash
aletheia version
```


## Configuration

### Azure OpenAI
Aletheia needs three environment variables to be set to work:

```bash
AZURE_OPENAI_API_KEY=<azure openai api key >
AZURE_OPENAI_ENDPOINT=<azure openai endpoint >
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=<azure deployment name>
```

### Additional configuration 

Aletheia supports flexible configuration via environment variables, YAML files, and .env files. The following table summarizes the main configuration parameters available in `aletheia/config.py`:

| Configuration Key | Description | Default Value |
|-------------------|-------------|---------------|
| `cost_per_input_token` | Cost per input token | `0.0` |
| `cost_per_output_token` | Cost per output token | `0.0` |
| `code_analyzer` | Code analyzer to use (claude, copilot) | `""` |
| `kubernetes_context` | Kubernetes context to use | `None` |
| `kubernetes_namespace` | Default Kubernetes namespace | `default` |
| `prometheus_endpoint` | Prometheus endpoint URL | `None` |
| `prometheus_credentials_type` | Prometheus credentials type | `env` |
| `prometheus_username_env` | Environment variable for Prometheus username | `None` |
| `prometheus_password_env` | Environment variable for Prometheus password | `None` |
| `prometheus_credentials_file` | Path to Prometheus credentials file | `None` |
| `prometheus_timeout_seconds` | Timeout for Prometheus requests in seconds | `10` |

**How to configure:**

- Set environment variables 
- Edit YAML config files (`./.aletheia/config.yaml`, `~/.aletheia/config.yaml`, `/etc/aletheia/config.yaml`)
- Use `.env` files for local overrides

See `aletheia/config.py` for advanced usage and helper methods.

