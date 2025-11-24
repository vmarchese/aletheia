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


## Skills (experimental)
Aletheia's skills are complex orchestration of the Aletheia's agents' tools that can be defined in external yaml files.
The skills must be in `<skill_folder>/<agent_name>` 

An example could be:
```yaml
---
name: Check IP in ELBV2 Security Groups
description: checks if a specific IP address is allowed by the security groups associated with ELBV2 load balancers in AWS.
instructions: |-
  Use this skill to check if a specific IP address is allowed by the security groups associated with ELBV2 load balancers in AWS.
  1. Use `aws_profiles()` to find the list of profiles
  2. If the user has specified a profile check against the results returned
  3. If the user has not specified a profile, ask him which one to use
  4. If the profile is there call `aws_elbv2_security_groups(profile)` to get the security groups associated with ELBV2 load balancers
  5. for each security group get the inbound rules using `aws_ec2_describe_security_group_inbound_rules(profile, group_id)`
  6. for each security group get the outbound rules using `aws_ec2_describe_security_group_outbound_rules(profile, group_id)`
  7. For each security group rule retrieved check if the specified IP address is allowed by the rule
  8. you MUST return the full results as a poem with rhymes in shakespearean style
```

If Aletheia is asked to  check if an IP address is allowed by the security group of and ELBV2 load balancer in AWS, it should recognize that it can't do it by simply invoking the given plugins and should load the skill to orchestrate the calls. 

When writing a skill try to avoid name overlapping with the Aletheia's plugins tool names

