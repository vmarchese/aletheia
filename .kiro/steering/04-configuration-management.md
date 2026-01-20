---
inclusion: always
---

# Configuration Management

## Configuration Hierarchy

Aletheia uses a prioritized configuration system with three layers:

1. **Environment Variables** (highest priority) - Prefixed with `ALETHEIA_`
2. **YAML Configuration File** - Platform-specific location
3. **Default Values** (lowest priority) - Built-in defaults

## Configuration File Locations

### Platform-Specific Paths

- **Linux**: `~/.config/aletheia/config.yaml`
- **macOS**: `~/Library/Application Support/aletheia/config.yaml`
- **Windows**: `%LOCALAPPDATA%\aletheia\config.yaml`

### Directory Structure

```
{config_dir}/aletheia/
├── config.yaml              # Main configuration
├── skills/                  # Skills directory
│   ├── aws/
│   │   └── skill_name/
│   │       └── instructions.yaml
│   └── kubernetes_data_fetcher/
│       └── skill_name/
│           └── instructions.yaml
└── instructions/            # Custom agent instructions
    ├── aws.txt
    ├── kubernetes_data_fetcher.txt
    └── orchestrator.txt
```

## Configuration Options

### LLM Configuration

```yaml
# Default LLM model for all agents
llm_default_model: gpt-4o

# Temperature for LLM responses (0.0-1.0)
# Lower = more deterministic, Higher = more creative
llm_temperature: 0.2

# Maximum tokens per response
llm_max_tokens: 4000

# Code analyzer preference (claude, copilot, or empty)
code_analyzer: claude
```

### Cost Tracking

```yaml
# Cost per 1M input tokens (in dollars)
cost_per_input_token: 0.0025

# Cost per 1M output tokens (in dollars)
cost_per_output_token: 0.01
```

### Prometheus Configuration

```yaml
# Prometheus server endpoint
prometheus_endpoint: https://prometheus.example.com

# Request timeout in seconds
prometheus_timeout_seconds: 30

# Credential storage type: env, keychain, encrypted_file
prometheus_credentials_type: env
```

### Directory Configuration

```yaml
# Custom skills directory (optional)
skills_directory: /path/to/custom/skills

# Custom instructions directory (optional)
custom_instructions_dir: /path/to/custom/instructions

# MCP servers configuration file (optional)
mcp_servers_yaml: /path/to/mcp-servers.yaml

# Temporary file storage
temp_folder: /tmp/aletheia
```

### Per-Agent Configuration

```yaml
agents:
  aws:
    model: gpt-4o
    temperature: 0.1
    max_tokens: 8000
  
  kubernetes_data_fetcher:
    model: gpt-4o-mini
    temperature: 0.2
    max_tokens: 4000
  
  code_analyzer:
    model: claude-3-5-sonnet-20241022
    temperature: 0.0
    max_tokens: 16000
```

## Environment Variables

All configuration can be set via environment variables with `ALETHEIA_` prefix:

### LLM Settings

```bash
export ALETHEIA_LLM_DEFAULT_MODEL=gpt-4o
export ALETHEIA_LLM_TEMPERATURE=0.2
export ALETHEIA_LLM_MAX_TOKENS=4000
export ALETHEIA_CODE_ANALYZER=claude
```

### Cost Settings

```bash
export ALETHEIA_COST_PER_INPUT_TOKEN=0.0025
export ALETHEIA_COST_PER_OUTPUT_TOKEN=0.01
```

### Prometheus Settings

```bash
export ALETHEIA_PROMETHEUS_ENDPOINT=https://prometheus.example.com
export ALETHEIA_PROMETHEUS_TIMEOUT_SECONDS=30
export ALETHEIA_PROMETHEUS_CREDENTIALS_TYPE=env
```

### Directory Settings

```bash
export ALETHEIA_SKILLS_DIRECTORY=/custom/path/to/skills
export ALETHEIA_CUSTOM_INSTRUCTIONS_DIR=/custom/path/to/instructions
export ALETHEIA_MCP_SERVERS_YAML=/path/to/mcp-servers.yaml
export ALETHEIA_TEMP_FOLDER=/tmp/aletheia
```

## LLM Provider Configuration

### OpenAI

```bash
export ALETHEIA_OPENAI_API_KEY=sk-...
export ALETHEIA_OPENAI_ENDPOINT=https://api.openai.com/v1
export ALETHEIA_OPENAI_MODEL=gpt-4o
```

### Azure OpenAI

```bash
export AZURE_OPENAI_API_KEY=your-api-key
export AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
export AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-4o
```

### Ollama (Local)

```bash
export ALETHEIA_OPENAI_API_KEY=none
export ALETHEIA_OPENAI_ENDPOINT=http://127.0.0.1:11434/v1
export ALETHEIA_OPENAI_MODEL=llama3:70b
```

### AWS Bedrock

```bash
# Use AWS credentials from environment or ~/.aws/credentials
export AWS_PROFILE=default
export AWS_REGION=us-east-1
export ALETHEIA_LLM_DEFAULT_MODEL=anthropic.claude-3-5-sonnet-20241022-v2:0
```

## Credential Management

### Storage Types

1. **Environment Variables** (`env`)
   - Store credentials in environment
   - Simple but less secure
   - Good for CI/CD and containers

2. **System Keychain** (`keychain`)
   - Use OS keychain (macOS Keychain, Windows Credential Manager, Linux Secret Service)
   - Most secure for local development
   - Requires user interaction on first use

3. **Encrypted File** (`encrypted_file`)
   - Store encrypted credentials in config directory
   - Encrypted with session password
   - Balance of security and convenience

### Setting Credentials

```bash
# Using environment variables
export PROMETHEUS_USERNAME=admin
export PROMETHEUS_PASSWORD=secret

# Using keychain (interactive)
aletheia config set-credential prometheus username admin
aletheia config set-credential prometheus password

# Using encrypted file
aletheia session open --encrypted
# Credentials stored in ~/.config/aletheia/credentials.enc
```

## Custom Instructions

### Per-Agent Instructions

Create custom instructions for specific agents:

```bash
# Create instructions file
cat > ~/.config/aletheia/instructions/aws.txt << EOF
- Always use us-west-2 region unless specified
- Prefer EC2 instance types with graviton processors
- Include cost estimates in recommendations
EOF
```

Instructions are loaded in order:
1. Built-in agent instructions
2. Agent's `instructions.md` file
3. Custom instructions from config directory

### Global Instructions

Apply instructions to all agents:

```bash
cat > ~/.config/aletheia/instructions/global.txt << EOF
- Always provide step-by-step reasoning
- Include confidence levels in analysis
- Suggest multiple solutions when possible
EOF
```

## Skills Configuration

### Skills Directory Structure

```
skills/
├── aws/
│   ├── check_security_groups/
│   │   ├── instructions.yaml
│   │   └── scripts/
│   │       └── analyze.py
│   └── cost_optimization/
│       └── instructions.yaml
└── kubernetes_data_fetcher/
    └── thread_dump_analysis/
        ├── instructions.yaml
        └── scripts/
            └── parse_dump.py
```

### Setting Skills Directory

```bash
# Via environment variable
export ALETHEIA_SKILLS_DIRECTORY=/path/to/skills

# Via config file
echo "skills_directory: /path/to/skills" >> ~/.config/aletheia/config.yaml
```

### Multiple Skills Directories

```bash
# Colon-separated list
export ALETHEIA_USER_SKILLS_DIRS=/path/to/skills1:/path/to/skills2
```

## MCP Server Configuration

### MCP Configuration File

Create `mcp-servers.yaml`:

```yaml
mcp_servers:
  # STDIO Transport
  - name: filesystem
    type: stdio
    agent: orchestrator
    description: File system operations
    command: uvx
    args:
      - mcp-server-filesystem
    env:
      LOG_LEVEL: ERROR
  
  # HTTP Streamable Transport
  - name: custom-api
    type: streamable_http
    agent: aws
    description: Custom API integration
    url: https://api.example.com/mcp
    bearer: ${MCP_API_TOKEN}
```

### Setting MCP Configuration

```bash
export ALETHEIA_MCP_SERVERS_YAML=/path/to/mcp-servers.yaml
```

## Configuration Validation

### Validate Configuration

```python
from aletheia.config import Config

# Load and validate
config = Config()

# Check required fields
assert config.llm_default_model is not None
assert config.llm_temperature >= 0.0 and config.llm_temperature <= 1.0

# Print current config
print(config.model_dump_json(indent=2))
```

### Common Validation Errors

1. **Invalid temperature**: Must be between 0.0 and 1.0
2. **Missing API keys**: Required for LLM providers
3. **Invalid paths**: Skills or instructions directories don't exist
4. **Invalid credential type**: Must be env, keychain, or encrypted_file

## Configuration Best Practices

1. **Use Environment Variables for Secrets**: Never commit API keys to config files
2. **Use Config Files for Preferences**: Model selection, temperature, directories
3. **Per-Environment Configs**: Different configs for dev, staging, production
4. **Version Control**: Commit `config.yaml.example`, not `config.yaml`
5. **Document Custom Settings**: Add comments explaining non-obvious settings

## Troubleshooting Configuration

### Check Current Configuration

```bash
# View active configuration
aletheia config show

# Check specific setting
aletheia config get llm_default_model
```

### Debug Configuration Loading

```python
import os
from aletheia.config import Config

# Enable debug logging
os.environ["ALETHEIA_DEBUG"] = "1"

# Load config
config = Config()

# Check sources
print(f"Config file: {config.config_file_path}")
print(f"Skills dir: {config.skills_directory}")
print(f"Model: {config.llm_default_model}")
```

### Common Issues

1. **Config not loading**: Check file path and permissions
2. **Environment variables ignored**: Ensure `ALETHEIA_` prefix
3. **Skills not found**: Verify skills directory path
4. **Credentials not working**: Check credential type and storage

## Example Configurations

### Development Setup

```yaml
llm_default_model: gpt-4o-mini
llm_temperature: 0.3
cost_per_input_token: 0.00015
cost_per_output_token: 0.0006
temp_folder: /tmp/aletheia-dev
```

### Production Setup

```yaml
llm_default_model: gpt-4o
llm_temperature: 0.1
cost_per_input_token: 0.0025
cost_per_output_token: 0.01
prometheus_endpoint: https://prometheus.prod.example.com
prometheus_credentials_type: keychain
temp_folder: /var/lib/aletheia
```

### Local Testing with Ollama

```yaml
llm_default_model: llama3:70b
llm_temperature: 0.2
cost_per_input_token: 0.0
cost_per_output_token: 0.0
```

```bash
export ALETHEIA_OPENAI_API_KEY=none
export ALETHEIA_OPENAI_ENDPOINT=http://127.0.0.1:11434/v1
export ALETHEIA_OPENAI_MODEL=llama3:70b
```
