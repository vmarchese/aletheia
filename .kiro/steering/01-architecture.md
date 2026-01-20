---
inclusion: always
---

# Aletheia Architecture

## Project Overview

Aletheia is a modular, AI-powered troubleshooting framework for SREs and system administrators. It orchestrates specialized LLM agents to collect and analyze observability data (logs, metrics, traces), inspect code, and generate actionable root cause hypotheses.

## Core Architecture

### Agent-Based System

Aletheia uses a multi-agent architecture where specialized agents handle different aspects of troubleshooting:

- **Orchestrator Agent**: Routes requests to appropriate specialist agents and coordinates their output
- **Data Fetcher Agents**: Kubernetes, AWS, Azure, Log Files, PCAP Files
- **Analysis Agents**: Code Analyzer, Security Agent, Network Agent
- **Specialized Agents**: AWS Managed Prometheus, SysDiag, Timeline

### Key Components

1. **Agent Framework** (`aletheia/agents/`)
   - Base agent class with common functionality
   - Agent client for LLM communication
   - Message store and history management
   - Skills system for complex orchestrations
   - Instructions loader for custom agent behavior

2. **Plugin System** (`aletheia/plugins/`)
   - Modular plugins for each agent's tools
   - Base plugin class for consistency
   - Plugin loader for dynamic discovery

3. **LLM Integration** (`aletheia/llm/`)
   - Supports multiple LLM providers (OpenAI, Azure OpenAI, Bedrock, Ollama)
   - Configurable per-agent model selection
   - Service layer for LLM interactions

4. **Session Management** (`aletheia/session.py`)
   - Encrypted session storage
   - Session persistence and export
   - Timeline tracking for investigations

5. **Knowledge Base** (`aletheia/knowledge/`)
   - ChromaDB-backed vector store
   - Semantic search for troubleshooting docs
   - Document management (add, delete, list)

6. **MCP Support** (`aletheia/mcp/`)
   - Model Context Protocol integration (experimental)
   - Per-agent MCP server configuration
   - STDIO and HTTP streamable transports

7. **Configuration** (`aletheia/config.py`)
   - Hierarchical config system (env vars, YAML, defaults)
   - Platform-aware config directories
   - Credential management

8. **CLI & UI** (`aletheia/cli.py`, `aletheia/ui/`)
   - Typer-based CLI with rich formatting
   - FastAPI-based web UI (alpha)
   - Interactive session commands

## Data Flow

1. User initiates session via CLI or Web UI
2. Orchestrator agent receives user query
3. Orchestrator routes to appropriate specialist agent(s)
4. Specialist agents use plugins to fetch data or perform actions
5. Agents analyze data using LLM reasoning
6. Results are formatted and returned to user
7. Session state is encrypted and persisted

## Extension Points

- **New Agents**: Extend `BaseAgent` in `aletheia/agents/`
- **New Plugins**: Extend `BasePlugin` in `aletheia/plugins/`
- **Skills**: YAML-based orchestrations in skills directory
- **Custom Instructions**: Per-agent instruction files
- **MCP Servers**: External tool integration via MCP protocol
