# Aletheia (ἀλήθεια)

> **Aletheia** (ἀλήθεια) — Ancient Greek for "truth" or "un-concealment": bringing what's hidden into the open.

Aletheia is a modular, AI-powered troubleshooting framework for SREs and system administrators. It orchestrates specialized LLM agents to collect and analyze observability data (logs, metrics, traces), inspect code, and generate actionable root cause hypotheses.

---

## Overview

Aletheia provides an interactive, agent-based workflow for troubleshooting distributed systems. It leverages Large Language Models (LLMs) and specialized plugins to automate data collection, pattern analysis, and root cause investigation across Kubernetes, Prometheus, log files, and more. The CLI offers a conversational interface for managing troubleshooting sessions, running investigations, and exploring demo scenarios.

### Available agents

- **Orchestrator** - Routes requests to appropriate specialist agents and relays their output
- **Kubernetes Data Fetcher** - Collects Kubernetes logs, pod information, and cluster health data
- **AWS Agent** - Manages AWS resources, logs, and AWS-specific investigations
- **AWS Managed Prometheus** - Handles AWS Managed Prometheus metrics, CPU/memory data, and PromQL queries
- **Azure Agent** - Manages Azure resources and performs Azure-specific queries and investigations
- **Code Analyzer** - Analyzes code repositories using Claude or GitHub Copilot for code review and inspection
- **Log File Data Fetcher** - Reads and analyzes local log files
- **PCAP File Data Fetcher** - Analyzes packet capture (PCAP) files for network troubleshooting
- **Network Agent** - Handles DNS queries, IP connectivity, port scanning, and general network tools
- **Security Agent** - Performs security testing and analysis using tools like httpx and sslscan
- **SysDiag Agent** - Provides system diagnostics and troubleshooting capabilities

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

### OpenaI (or Ollama)
To use Aletheia with ollama the following environment variables must be set:

```bash
ALETHEIA_OPENAI_API_KEY=<openai api key>
ALETHEIA_OPENAI_ENDPOINT=<openai endpoint>
ALETHEIA_OPENAI_MODEL=<openai model>
```

For instance, to use ollama on the local machine:

```bash
ALETHEIA_OPENAI_API_KEY=none 
ALETHEIA_OPENAI_ENDPOINT=http://127.0.0.1:11434/v1
ALETHEIA_OPENAI_MODEL=gpt-oss:20b
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


## Custom Instructions
Custom instructions for the specific agents can be set by configuring the environment variable `ALETHEIA_CUSTOM_INSTRUCTIONS_DIR` to a folder in which the instructions can be written as:

```
<custom instructions dir>
   |-- <agent name>
          |-- instructions.md
```          

For instance, for the Kubernetes agent.


```
<custom instructions dir>
   |-- kubernetes_data_fetcher
          |-- instructions.md
```          

in which `instructions.md` could be:

```markdown
- ALWAYS answer in rhymes
- ALWAYS add a funny kubernetes koke at the end
```



## Skills (experimental)
Aletheia's skills are complex orchestration of the Aletheia's agents' tools that can be defined in external yaml files.
The skills must be in `<skill_folder>/<agent_name>/<skill_name>` 

Where `<skill_folder>` can be set with the environment variable `ALETHEIA_USER_SKILLS_DIRS`

An example could be:
```
<skill_folder>
  |--aws
      <skill name>
        |-- instructions.yaml
        |--scripts
              |-- myscript.py
```      
in which `instructions.yaml` is: 

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

### Python scripts execution

You can add some python scripts to the skills and ask Aletheia to execute them if the skill is loaded. The scripts are executed in a docker container. 

1. **Build the docker image**

Build the aletheia-script-executor image from `aletheia-script-executor/Dockerfile`
```
cd aletheia-script-executor
docker build -t aletheia:latest .
```

2. **Add your scripts to the `<skill_folder>/<your skill>/scripts` folder**

e.g.:
```
<skills folder>
  |-- kubernetes_data_fetcher
        |--awesome_skill
              |-- instructions.yaml
              |-- scripts
                     |-- myscript.py
```

where `myscript.py` is

```python
import os

my_variable = os.environ.get("MY_VARIABLE")
print("Here's the pod in pending state:", my_variable)
```

3. **Reference your script from the skill instructions and ask Aletheia to inject variables**

```yaml
---
name: My Awesome Kubernetes skill
description: An awesome Kubernetes skill 
instructions: |-
  Use this awesome skill to find a pending pod in the kubernetes cluster:
  1. list the pods in the namespace with `list_kubernetes_pods()`
  2. Find the name of the pod that is in a `Pending` state
  3. call the script `myscript.py` passing as a parameter my_variable=<name of the pending pod>
```

4. **Run Aletheia**

```
> aletheia session open --unsafe -vv
[INC-25E3] 👤 YOU: execute my awesome skill for kubernetes in namespace aletheia-test

[INC-25E3] 🤖 Aletheia
────────────────────────────────────────────────────────────────────────────────
Loading skill from: [...]/test_skills/kubernetes_data_fetcher/awesome_skill
AGENT: kubernetes_data_fetcher

─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
Section Findings:

 • Listed all pods in namespace aletheia-test using list_kubernetes_pods(). Found the following pods:
    • golang-test-service-6c6787f8dc-jmmfr (Running)
    • golang-test-service-6c6787f8dc-wnf5b (Running)
    • java-test-service-5cdf59696b-8bzr2 (Running)
    • java-test-service-5cdf59696b-t4lkc (Running)
    • ms-call-6579c46bdf-5gmb9 (Running)
    • ms-call-6579c46bdf-vl5zm (Running)
    • ms-called-b8f45d8c7-9xdz6 (Running)
    • ms-called-b8f45d8c7-ftmpc (Running)
    • pod-with-missing-secret (Pending)
 • Found the pod in Pending state: pod-with-missing-secret.
 • Executed the script myscript.py from the skill, passing my_variable=pod-with-missing-secret.
 • Script output: "Here's the pod in pending state: pod-with-missing-secret"

Section Decisions:

 • Loaded the skill "My Awesome Kubernetes skill" as requested, following the instructions exactly.
 • Used list_kubernetes_pods() to get all pods in the namespace, identified the pending pod, and executed the required script with the pod name as parameter.
 • Did not use direct tool calls beyond those required by the skill instructions.

Section Suggested actions:

 • If you need further investigation on why the pod is pending, consider describing the pod or checking events for pod-with-missing-secret.

─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
You can ask questions about the investigation or type 'exit' to end the session.
```

## WEB UI (Alpha)
Aletheia has a very rudimental WEB UI. To access it start Aletheia with `aletheia serve` and open `http://localhost:8000` in your browser.

## MCP Support (Highly experimental)
You can add MCP Server to each agent by setting a `ALETHEIA_MCP_SERVERS_YAML` env variable pointing to a yaml configuration which must have the following format:

```yaml
mcp_servers:
  # STDIO Transport
  - name: # MCP Server Name
    type: stdio # if stdio 
    agent: # name of the agent that will access the server
    description: # mcp server description
    command: # mcp servert command. e.g.: uvx
    args:  # array of arguments
    env: # dictionary ov environment variables
    ...
  # HTTP Streamable Transport
  - name: # MCP Server Name
    type: streamable_http # if stdio 
    agent: # name of the agent that will access the server
    description: # mcp server description
    url: # uri of the server
    bearer:  # bearer token
    ...
```


 

