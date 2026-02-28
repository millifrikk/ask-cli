# Product Requirements Document: Ask CLI - Terminal AI Assistant

**Version:** 2.0  
**Date:** February 28, 2026  
**Author:** Emil  
**Status:** Draft

---

## 1. Executive Summary

**Ask CLI** is an intelligent terminal assistant that brings LLM capabilities directly into the command line. It enables developers, system administrators, and technical users to get instant answers, debug issues, analyze logs, and execute complex tasks without leaving the terminal environment.

The tool leverages Z.ai's Coding Plan subscription through their Anthropic-compatible API, providing cost-effective access to powerful AI models (GLM-4.5, GLM-5) for everyday terminal workflows.

---

## 2. Product Vision

**Mission:** Eliminate context-switching and reduce time-to-solution for technical users by embedding intelligent assistance directly into the terminal workflow.

**Target Users:**
- Software developers and DevOps engineers
- System administrators
- SAP consultants and EWM specialists
- Database administrators
- Anyone who spends significant time in the terminal

**Value Proposition:**
- Zero context switching - get help without leaving terminal
- Cost-effective - uses existing Z.ai Coding Plan subscription
- Flexible input - text queries, piped commands, file analysis
- Domain expertise - specialized modes for SAP, Docker, SQL, etc.

---

## 3. Current Features (v1.0)

### 3.1 Core Functionality
| Feature | Description | Status |
|---------|-------------|--------|
| **Direct Questions** | Ask any question directly from command line | ✅ Implemented |
| **Piped Input** | Accept stdin for command output analysis | ✅ Implemented |
| **Z.ai Integration** | Uses Coding Plan subscription via Anthropic API | ✅ Implemented |
| **Simple Invocation** | Single command: `ask "question"` | ✅ Implemented |

### 3.2 Technical Implementation
- **Language:** Python 3
- **Dependencies:** anthropic SDK
- **Authentication:** Z.ai API key + Anthropic base URL
- **Model:** GLM models via claude-sonnet-4-5-20250929 endpoint
- **Installation:** `~/bin/ask` executable script
- **Token Limit:** 1024 tokens max per response

### 3.3 Current Usage Examples
```bash
# Direct questions
ask "how do I list files by modification time?"

# Piped input
docker ps | ask "explain these containers"
cat error.log | ask "what's causing this error?"
```

---

## 4. Proposed Features (v2.0)

### 4.1 Multi-Provider Support

**Priority:** High  
**Effort:** High

**Description:**  
Support multiple LLM providers (Z.ai, Anthropic, OpenAI, Google Gemini, Ollama) with easy switching between providers and models. Users can configure API keys for each provider and select based on cost, capability, or availability needs.

**Supported Providers:**

| Provider | Models | Pricing (per 1M tokens) | Notes |
|----------|--------|------------------------|-------|
| **Z.ai** | GLM-5, GLM-4.7, GLM-4.7-Flash | Via Coding Plan subscription | Current default, most cost-effective |
| **Anthropic** | Claude Sonnet 4.5, Claude Opus 4.5, Claude Haiku 4.5 | Input: $3-15, Output: $15-75 | Highest quality, expensive |
| **OpenAI** | GPT-4o, GPT-4o-mini, o1 | Input: $2.50-15, Output: $10-60 | Good general purpose |
| **Google Gemini** | Gemini 2.5 Pro, 2.5 Flash, Flash-Lite | Input: $0.075-1.25, Output: $0.30-5 | Very affordable, good balance |
| **Ollama** | Llama 3.2, Qwen 2.5, CodeLlama, Mistral | Free (local) | Fully offline, no API costs |

**Configuration Structure:**
```json
{
  "providers": {
    "zai": {
      "api_key": "your-zai-key",
      "base_url": "https://api.z.ai/api/anthropic",
      "models": ["glm-5", "glm-4.7", "glm-4.7-flash"],
      "default_model": "glm-5"
    },
    "anthropic": {
      "api_key": "your-anthropic-key",
      "models": ["claude-sonnet-4-5", "claude-opus-4-5", "claude-haiku-4-5"],
      "default_model": "claude-sonnet-4-5"
    },
    "openai": {
      "api_key": "your-openai-key",
      "models": ["gpt-4o", "gpt-4o-mini", "o1"],
      "default_model": "gpt-4o-mini"
    },
    "google": {
      "api_key": "your-google-key",
      "models": ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-flash-lite"],
      "default_model": "gemini-2.5-flash"
    },
    "ollama": {
      "base_url": "http://localhost:11434",
      "models": ["llama3.2", "qwen2.5-coder", "codellama"],
      "default_model": "llama3.2"
    }
  },
  "default_provider": "zai"
}
```

**Flags:**
- `-p, --provider <n>`: Select provider (zai, anthropic, openai, google, ollama)
- `-m, --model <n>`: Explicitly specify model
- `--fast`: Use fastest/cheapest model for provider *(no short form - `-f` reserved for `--file`)*
- `--smart`: Use best/reasoning model for provider *(no short form reserved for future use)*
- `--list-providers`: Show configured providers
- `--list-models`: Show available models for current provider

**Implementation Details:**
```python
# Provider abstraction layer
class ProviderManager:
    def __init__(self, config):
        self.providers = {
            'zai': ZaiProvider(config['zai']),
            'anthropic': AnthropicProvider(config['anthropic']),
            'openai': OpenAIProvider(config['openai']),
            'google': GoogleProvider(config['google']),
            'ollama': OllamaProvider(config['ollama'])
        }
    
    def get_provider(self, name):
        return self.providers.get(name)
    
    def select_model(self, provider, preference='default'):
        # Maps -f, -s flags to provider-specific models
        model_map = {
            'zai': {'fast': 'glm-4.7-flash', 'smart': 'glm-5'},
            'anthropic': {'fast': 'claude-haiku-4-5', 'smart': 'claude-opus-4-5'},
            'openai': {'fast': 'gpt-4o-mini', 'smart': 'o1'},
            'google': {'fast': 'gemini-flash-lite', 'smart': 'gemini-2.5-pro'},
            'ollama': {'fast': 'llama3.2', 'smart': 'qwen2.5-coder'}
        }
        return model_map[provider].get(preference, 'default')
```

**Use Cases:**
```bash
# Use default (Z.ai)
ask "what's the syntax for grep?"

# Switch providers
ask -p google "explain kubernetes"              # Use Gemini
ask -p anthropic "complex reasoning task"       # Use Claude
ask -p ollama "quick question"                  # Use local Ollama

# Specify exact model
ask -p openai -m gpt-4o "advanced coding task"
ask -p google -m gemini-flash-lite "bulk processing"

# Use smart/fast shortcuts
ask --fast "simple lookup"                      # Fast model (GLM-4.7-flash)
ask --smart "complex reasoning"                 # Smart model (GLM-5)
ask -p google --fast "cheap bulk task"          # Google Flash-Lite

# List available options
ask --list-providers
ask --list-models
ask -p anthropic --list-models                  # Models for specific provider

# Set new default provider
ask --set-default-provider google
```

**Provider Setup:**
```bash
# Interactive provider setup
ask --add-provider google
Enter Google API key: ****
Test connection... ✓ Connected
Added provider 'google' with models: gemini-2.5-pro, gemini-2.5-flash, gemini-flash-lite

# View current configuration
ask --show-providers
╭─ Configured Providers ──────────────────╮
│ ✓ zai (default)                          │
│   Models: glm-5, glm-4.7-flash           │
│   Status: Connected                      │
│                                          │
│ ✓ google                                 │
│   Models: gemini-2.5-flash, ...          │
│   Status: Connected                      │
│                                          │
│ ✗ anthropic                              │
│   Status: Not configured                 │
╰──────────────────────────────────────────╯
```

**Model Deprecation Handling:**

The tool periodically checks provider model status pages to detect deprecated models and suggest migrations.

**Model Status Sources:**
- **Anthropic:** https://docs.anthropic.com/en/docs/about-claude/models
- **OpenAI:** https://platform.openai.com/docs/deprecations
- **Google:** https://ai.google.dev/gemini-api/docs/models
- **Z.ai:** https://docs.z.ai/guides/overview/quick-start

**Deprecation Warning Example:**
```bash
$ ask "test query"
⚠️  Warning: Model 'glm-4.5' is deprecated (EOL: March 2026)
   Recommended: Upgrade to 'glm-5' (better performance, same cost)
   
   Update config now? [y/N]: y
   ✓ Updated default model to 'glm-5'
```

### 4.2 Conversation History (Multi-Turn)

**Priority:** High  
**Effort:** Medium

**Description:**  
Enable multi-turn conversations where context is preserved across queries.

**Flags:**
- `-c, --continue`: Continue previous conversation
- `--history`: Show conversation history
- `--clear`: Clear conversation history

**Implementation Details:**
- Store conversation in `~/.local/share/ask/history.json`
- Each conversation gets unique session ID
- Auto-expire after 1 hour or manual clear
- Max context window management

**Storage Format:**
```json
{
  "session_id": "abc123",
  "timestamp": "2026-02-28T10:30:00",
  "messages": [
    {"role": "user", "content": "what are docker volumes?"},
    {"role": "assistant", "content": "Docker volumes are..."},
    {"role": "user", "content": "give me an example"}
  ]
}
```

**Use Cases:**
```bash
ask "what are kubernetes pods?"
ask -c "how do they differ from docker containers?"
ask -c "show me a pod yaml example"
ask --clear  # Start fresh
```

---

### 4.3 Output Formatting Options

**Priority:** Medium
**Effort:** Low

**Description:**
Control output format for better integration with other tools and workflows.

**Flags:**
- `--markdown`: Format output as markdown
- `--json`: Return structured JSON
- `--code-only`: Extract only code blocks, no explanations
- `--raw`: Raw output without formatting
- `--quick`: Terse mode - return the shortest useful answer only (see below)

**`--quick` flag:**
Instructs the model to respond with the most concise answer possible. For commands, return only the command. For factual questions, return one sentence. Sets a low token ceiling internally. Ideal for "muscle memory" lookups where you just want the answer without explanation.

```bash
ask --quick "find a file by name in any subdirectory"
# Returns: find . -name "myfile.txt"

ask --quick "grep case insensitive flag"
# Returns: -i

ask --quick "restart nginx"
# Returns: sudo systemctl restart nginx
```

**Implementation Details:**
- Parse response and extract relevant sections
- Use regex/parsing for code block extraction
- JSON mode includes system prompt for structured output
- `--quick` appends system instruction: *"Give the shortest possible answer. For commands, return only the command. No explanation unless critical."* and caps `max_tokens` at 256.

**Use Cases:**
```bash
ask --code-only "python function to parse CSV" > script.py
ask --json "list top 5 linux distros" | jq '.distros[0]'
ask --markdown "git workflow guide" > git-guide.md
ask --quick "how do I list files sorted by date?"
```

---

### 4.4 Template/Prompt Library

**Priority:** High  
**Effort:** Medium

**Description:**  
Pre-built prompt templates optimized for common tasks.

**Built-in Templates:**
- `--explain <command>`: Explain what a command does
- `--fix <error>`: Suggest fixes for error messages
- `--optimize <code/query>`: Optimization suggestions
- `--translate-to <language>`: Code translation
- `--review`: Code review with best practices
- `--debug`: Debugging assistance
- `--document`: Generate documentation

**Custom Templates:**
- Store in `~/.local/share/ask/templates/`
- User can create custom templates
- Template variables using `{{variable}}` syntax

**Template File Format:**
```yaml
# ~/.local/share/ask/templates/sap-transport.yaml
name: sap-transport
description: SAP transport request helper
prompt: |
  You are an SAP expert. The user is asking about transport requests.
  Context: SAP ECC/S4HANA environment
  Focus on: {{focus|default:general}}
  
  User question: {{query}}
```

**Use Cases:**
```bash
ask --explain "tar -xzvf archive.tar.gz"
ask --fix "bash: command not found: npm"
ask --optimize "SELECT * FROM users WHERE status='active'"
ask --translate-to python < script.sh
```

---

### 4.5 Context-Aware File Attachments

**Priority:** High  
**Effort:** Medium

**Description:**  
Analyze files directly by passing them as context to the LLM.

**Flags:**
- `-f <file>, --file <file>`: Attach single file
- `-F <pattern>, --files <pattern>`: Attach multiple files via glob
- `--max-file-size <size>`: Limit file size (default: 100KB)

**Supported File Types:**
- Text files (.txt, .log, .md)
- Code files (.py, .js, .java, .yaml, .json, .xml)
- Config files (.conf, .ini, .env)
- SQL files (.sql)
- Dockerfile, docker-compose.yml
- Auto-detect based on extension

**Implementation Details:**
- Read file contents and prepend to query
- Add file metadata (name, size, type)
- Truncate if exceeds token limits
- Warning if file too large

**Use Cases:**
```bash
ask -f config.yaml "is this kubernetes config valid?"
ask -f error.log "what's causing these errors?"
ask -F "*.py" "review this module for bugs"
ask -f Dockerfile "optimize this for production"
```

---

### 4.6 Interactive Mode (REPL)

**Priority:** Deferred
**Effort:** Medium
**Status:** ⏸ Deferred - superseded by `-c` (continue) flag

**Rationale for deferral:**
After evaluation, the `-c/--continue` flag (section 4.2) covers the core multi-turn use case more effectively for terminal power users. The key insight: interactive mode traps the user inside a REPL and breaks the natural terminal workflow of running shell commands and piping their output into `ask`. With `-c`, users stay at their shell prompt and can freely interleave real commands with follow-up questions:

```bash
# This natural flow works with -c, not possible inside a REPL
docker logs my-app 2>&1 | ask "what's failing?"
kubectl describe pod my-pod | ask -c "is this related to the error above?"
ask -c "how do I fix it?"
```

Interactive mode may be reconsidered in v3.0 if there is strong user demand for a dedicated session-based workflow (e.g., with shell-escape support).

**Original flags (reserved, not implemented):**
- `-i, --interactive`: Start interactive mode *(flag reserved, not implemented)*

---

### 4.7 Shell Command Suggestions with Safety

**Priority:** High  
**Effort:** Medium

**Description:**  
Generate executable shell commands with safety confirmation before execution.

**Flags:**
- `--cmd`: Request executable command (with safety prompt)
- `--execute`: Auto-execute without confirmation (dangerous)
- `--dry-run`: Show command but never execute

**Safety Features:**
- Highlight destructive commands (rm, dd, mkfs, etc.)
- Require explicit confirmation
- Log all executed commands to `~/.local/share/ask/executed_commands.log`
- Never auto-execute destructive operations

**Implementation Details:**
```python
DESTRUCTIVE_COMMANDS = ['rm', 'dd', 'mkfs', 'fdisk', 'parted', 'kill', 'shutdown']

def is_destructive(command):
    return any(cmd in command for cmd in DESTRUCTIVE_COMMANDS)
```

**Use Cases:**
```bash
$ ask --cmd "find all node_modules folders"
Generated command:
  find . -type d -name "node_modules"

Execute this command? [y/N]: y
./project1/node_modules
./project2/node_modules

$ ask --cmd "delete all .log files older than 30 days"
⚠️  WARNING: Destructive command detected!
Generated command:
  find . -name "*.log" -mtime +30 -delete

This will DELETE files. Type 'yes' to confirm: yes
[Executes...]
```

---

### 4.8 Specialized Domain Modes

**Priority:** High  
**Effort:** Medium

**Description:**  
Pre-configured modes with domain expertise for specific technical areas.

**Specialized Modes:**

| Mode | Flag | Expertise Area |
|------|------|----------------|
| SAP | `--sap` | SAP ECC, S/4HANA, EWM, transport management |
| Docker | `--docker` | Containers, images, compose, optimization |
| SQL | `--sql` | Query optimization, database design |
| Git | `--git` | Version control, branching strategies |
| AWS | `--aws` | Cloud infrastructure, services |
| Kubernetes | `--k8s` | Orchestration, deployments, troubleshooting |
| Security | `--security` | Security analysis, vulnerabilities |
| Performance | `--perf` | Performance optimization, profiling |

**Implementation Details:**
- Each mode has custom system prompt
- Domain-specific context and terminology
- Relevant best practices and patterns

**System Prompt Examples:**
```python
DOMAIN_PROMPTS = {
    'sap': """You are an expert SAP consultant specializing in:
        - SAP ECC and S/4HANA
        - SAP EWM (Extended Warehouse Management)
        - Transport management (STMS, SE09, SE10)
        - ABAP development
        - SAP Basis administration
        
        Provide concise, practical answers focused on SAP environments.
        Reference transaction codes and SAP-specific terminology.
        """,
    
    'docker': """You are a Docker and containerization expert.
        Focus on:
        - Docker best practices and optimization
        - Dockerfile efficiency
        - docker-compose configurations
        - Container security and networking
        - Volume management and persistence
        
        Provide production-ready solutions.
        """
}
```

**Use Cases:**
```bash
ask --sap "how do I check EWM queue status?"
ask --docker "optimize this Dockerfile" < Dockerfile
ask --sql "explain this query plan" < query.sql
ask --k8s "why is my pod in CrashLoopBackOff?"
```

---

### 4.9 Terminal Action Agent

**Priority:** Medium  
**Effort:** High

**Description:**  
Advanced agentic mode where the AI can execute multi-step workflows with user approval.

**Capabilities:**
- Execute multiple commands in sequence
- Analyze command output and decide next steps
- Request user approval at decision points
- Handle errors and retry with modifications

**Flags:**
- `--agent`: Enable agent mode
- `--auto-approve`: Auto-approve non-destructive commands
- `--agent-max-steps <n>`: Limit agent to n steps (default: 10)

**Safety:**
- Always show plan before execution
- Require approval for each step
- Log all agent actions
- Timeout after max steps

**Workflow:**
```
1. User provides goal
2. Agent creates execution plan
3. User approves plan
4. Agent executes steps, showing output
5. Agent analyzes results
6. Agent continues or requests next approval
```

**Use Cases:**
```bash
$ ask --agent "analyze my docker environment and suggest cleanup"

📋 Agent Plan:
  1. List all docker containers (running + stopped)
  2. Check disk usage of images
  3. Identify unused volumes
  4. Generate cleanup script
  5. Ask for approval to execute

Approve this plan? [y/N]: y

Step 1/5: Listing containers...
  ✓ Found 12 containers (3 running, 9 stopped)

Step 2/5: Checking image disk usage...
  ✓ Total: 4.2 GB across 8 images

Step 3/5: Checking volumes...
  ✓ Found 3 unused volumes (1.1 GB)

Step 4/5: Generating cleanup script...
  ✓ Created cleanup.sh

Cleanup will:
  - Remove 9 stopped containers
  - Remove 3 unused volumes
  - Remove 2 dangling images
  - Free up ~2.3 GB

Execute cleanup? [y/N]: 
```

---

### 4.10 Knowledge Base / RAG Integration

**Priority:** Deferred (v3.0+)
**Effort:** High
**Status:** ⏸ Deferred - planned as an optional extra, not part of core install

**Rationale for deferral:**
RAG requires heavy dependencies (`chromadb`, `sentence-transformers`) that total ~2GB and require a local embedding model. This is inappropriate for a core CLI tool install. For v2.0, file attachments (`-f`, `-F` flags) cover most real-world use cases without any indexing overhead.

When implemented, this will be a separately installable extra:
```bash
pip install ask-cli[rag]
```

**Planned Flags (reserved, not implemented in v2.0):**
- `--index <path>`: Index a directory
- `--kb <name>`: Query specific knowledge base
- `--list-kb`: List all knowledge bases
- `--reindex <name>`: Re-index knowledge base

**Storage Structure (planned):**
```
~/.config/ask/kb/
├── baton/
│   ├── index.db
│   ├── config.json
│   └── embeddings/
└── sap-notes/
```

---

### 4.11 Streaming Output

**Priority:** High *(moved from Low - foundational UX feature)*
**Effort:** Low *(with `rich` already in stack, near-zero extra effort)*
**Phase:** 1

**Description:**
Display response tokens as they're generated rather than waiting for full completion. This is a foundational UX feature - the tool should feel alive, not frozen. Implemented via `rich.live` with the Anthropic streaming API.

**Benefits:**
- Dramatically faster perceived response time
- User can interrupt early if the answer becomes clear (Ctrl+C)
- No regression vs. current tool's blocking behaviour
- Sets up the streaming infrastructure needed by agent mode later

**Implementation Details:**
- Use Anthropic's streaming API (`client.messages.stream()`)
- Render via `rich.live` for clean terminal updates
- Handle `KeyboardInterrupt` (Ctrl+C) gracefully - print partial response and exit cleanly
- Streaming is **always on** - no flag needed

**Use Cases:**
```bash
$ ask "explain kubernetes architecture in detail"
Kubernetes is a container orchestration platform that...█
[Tokens appear as generated, Ctrl+C stops early]
```

---

### 4.12 Usage Tracking & Statistics

**Priority:** Low  
**Effort:** Low

**Description:**  
Track usage, costs, and quota consumption.

**Metrics Tracked:**
- Number of queries per day/week/month
- Tokens consumed (input/output)
- Estimated cost (if applicable)
- Most used features/modes
- Response time statistics

**Flags:**
- `--stats`: Show usage statistics
- `--stats-reset`: Reset statistics

**Storage:**
```json
{
  "total_queries": 1247,
  "total_tokens_input": 45231,
  "total_tokens_output": 123456,
  "queries_by_mode": {
    "default": 1100,
    "sap": 89,
    "docker": 58
  },
  "first_use": "2026-02-01",
  "last_use": "2026-02-28"
}
```

**Use Cases:**
```bash
$ ask --stats
╭─ Ask CLI Statistics ────────────────╮
│ Total Queries:        1,247         │
│ This Month:           342            │
│ Tokens Used:          168,687        │
│ Most Used Mode:       default (88%)  │
│ Average Response:     1.2s           │
│                                      │
│ Top Commands:                        │
│  1. Direct questions   (78%)         │
│  2. Piped input        (15%)         │
│  3. File analysis      (7%)          │
╰──────────────────────────────────────╯
```

---

### 4.13 Syntax Highlighting

**Priority:** Low  
**Effort:** Low

**Description:**  
Automatically highlight code blocks in terminal output.

**Implementation:**
- Use `pygments` library
- Auto-detect language in code blocks
- Configurable color schemes
- Disable with `--no-color`

**Use Cases:**
```bash
ask "python function to read CSV"
# Output has syntax-highlighted Python code
```

---

### 4.14 Clipboard Integration

**Priority:** Low  
**Effort:** Low

**Description:**  
Copy results directly to clipboard.

**Flags:**
- `--copy`: Copy entire response to clipboard
- `--copy-code`: Copy only code blocks to clipboard

**Implementation:**
- Use `pyperclip` or `xclip` (Linux)
- Auto-detect clipboard tool availability
- Notify user when copied

**Use Cases:**
```bash
ask --copy "docker compose for postgres + redis"
# Output: "✓ Copied to clipboard"

ask --copy-code "python web scraper with requests"
# Copies only the Python code, not explanation
```

---

### 4.15 Save & Recall Responses

**Priority:** Medium  
**Effort:** Low

**Description:**  
Save useful responses for later reference.

**Flags:**
- `--save <name>`: Save response with name
- `--recall <name>`: Recall saved response
- `--list-saved`: List all saved responses
- `--delete-saved <name>`: Delete saved response

**Storage:**
```json
{
  "git-cheatsheet": {
    "query": "common git commands",
    "response": "Here are the most common git commands...",
    "timestamp": "2026-02-28T10:30:00",
    "tags": ["git", "reference"]
  }
}
```

**Use Cases:**
```bash
ask --save git-cheatsheet "common git commands"
# ✓ Saved as 'git-cheatsheet'

ask --list-saved
# git-cheatsheet (2 days ago)
# docker-networks (1 week ago)
# sap-transport-codes (3 weeks ago)

ask --recall git-cheatsheet
# [Shows previously saved response]
```

---

### 4.16 Voice Input

**Priority:** Removed
**Status:** ❌ Removed from roadmap

**Rationale:**
Voice input (`sounddevice`, `whisper`) adds significant dependency weight with minimal practical value for a terminal-first tool. Terminal power users have fast keyboard workflows; voice input introduces latency and environmental constraints (microphone, noise) that conflict with the tool's core use case. Removed from all phases.


### 4.17 Offline Mode with Local Models

**Priority:** High  
**Effort:** Medium

**Description:**  
Support fully offline operation using local LLM providers for privacy-conscious users, air-gapped environments, or to eliminate API costs.

**Supported Local Providers:**
- **Ollama** (recommended) - Easy setup, great UX
- **llama.cpp** - Lightweight, minimal dependencies  
- **GPT4All** - Cross-platform GUI option
- **LocalAI** - OpenAI-compatible API server

**Benefits:**
- **Complete Privacy:** Data never leaves your machine
- **Zero API Costs:** No per-token charges
- **No Internet Required:** Works offline
- **Low Latency:** No network roundtrips
- **Air-Gapped Ready:** For secure/isolated environments

**Setup - Ollama (Recommended):**
```bash
# Automated setup
ask --setup-offline
Choose offline provider:
  1. Ollama (recommended)
  2. llama.cpp
  3. GPT4All
  4. LocalAI
  
Selection [1]: 1

Installing Ollama...
✓ Ollama installed

Downloading recommended models...
✓ llama3.2 (2.0 GB) - General purpose
✓ qwen2.5-coder (4.7 GB) - Coding specialist
✓ mistral (4.1 GB) - Fast and capable

Offline mode ready!

# Manual Ollama setup
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2
ollama pull qwen2.5-coder

# Configure in Ask CLI
ask --add-provider ollama
Ollama base URL [http://localhost:11434]: 
✓ Connected to Ollama
Available models: llama3.2, qwen2.5-coder, mistral

# Make it default
ask --set-default-provider ollama
```

**Model Selection for Offline:**

| Model | Size | Best For | Speed |
|-------|------|----------|-------|
| **llama3.2** | 2 GB | General Q&A, summaries | Fast |
| **qwen2.5-coder:7b** | 4.7 GB | Coding, technical queries | Medium |
| **mistral:7b** | 4.1 GB | Balanced performance | Fast |
| **codellama:13b** | 7.3 GB | Advanced coding | Slower |
| **llama3.2:70b** | 40 GB | Best quality (needs powerful GPU) | Slow |

**Usage:**
```bash
# Use offline mode
ask -p ollama "how do I use rsync?"
ask -p ollama -m qwen2.5-coder "explain this Python code" < script.py

# Quick offline alias
alias askoff='ask -p ollama'
askoff "what's the difference between TCP and UDP?"

# Check what models are available locally
ask -p ollama --list-models
Available local models:
  • llama3.2 (2.0 GB)
  • qwen2.5-coder (4.7 GB) 
  • mistral (4.1 GB)

# Download more models
ollama pull llama3.2:70b
ollama pull codellama:13b
```

**Configuration:**
```json
{
  "providers": {
    "ollama": {
      "base_url": "http://localhost:11434",
      "models": ["llama3.2", "qwen2.5-coder", "mistral"],
      "default_model": "llama3.2",
      "offline": true
    }
  },
  "offline_fallback": {
    "enabled": true,
    "provider": "ollama",
    "message": "Using offline model - Internet unavailable"
  }
}
```

**Automatic Offline Fallback:**
```bash
# If primary provider (Z.ai) fails, automatically use Ollama
$ ask "test query"
⚠️  Unable to connect to Z.ai API
✓ Falling back to offline provider (Ollama)
[Response from local model...]

# Configure fallback behavior
ask --set-offline-fallback enabled
Offline fallback enabled. Will use 'ollama' when API unavailable.
```

**Performance Comparison:**

| Provider | Response Time | Quality | Cost | Privacy |
|----------|---------------|---------|------|---------|
| Z.ai GLM-5 | 1-3s | Excellent | Subscription | Moderate |
| Gemini Flash | 1-2s | Very Good | Very Low | Moderate |
| Ollama Llama3.2 | 0.5-2s | Good | Free | Complete |
| Ollama Qwen2.5 | 1-3s | Very Good (code) | Free | Complete |

**Resource Requirements:**

| Model Size | RAM Required | GPU Recommended | Disk Space |
|------------|--------------|-----------------|------------|
| 7B models | 8 GB | Optional (faster) | 4-5 GB |
| 13B models | 16 GB | Recommended | 7-8 GB |
| 70B models | 64 GB | Required (24GB VRAM) | 40 GB |

**Use Cases:**
- **Air-gapped environments:** Government, finance, healthcare
- **Privacy-sensitive work:** Legal, confidential business
- **Cost optimization:** High-volume usage scenarios
- **Remote/offline work:** Travel, areas with poor connectivity
- **Development/testing:** Local development without API costs

---

## 5. Technical Architecture

### 5.1 System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Ask CLI v2.0                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   CLI Parser │  │ Input Handler│  │ Output       │      │
│  │   (argparse) │→ │ (stdin/files)│→ │ Formatter    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         ↓                  ↓                  ↑               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Template   │  │  Context     │  │  Response    │      │
│  │   Manager    │→ │  Builder     │→ │  Processor   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         ↓                  ↓                  ↑               │
│  ┌──────────────┐  ┌──────────────┐          │              │
│  │   Session    │  │   API Client │──────────┘              │
│  │   Manager    │  │   (Anthropic)│                         │
│  └──────────────┘  └──────────────┘                         │
│         ↓                  ↓                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Local       │  │   Agent      │  │  Knowledge   │      │
│  │  Storage     │  │   Executor   │  │  Base (RAG)  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                               │
└─────────────────────────────────────────────────────────────┘
         ↓                       ↓                       ↓
┌──────────────┐        ┌──────────────┐       ┌──────────────┐
│ ~/.config/   │        │  Z.ai API    │       │  Local Files │
│  ask/ + data │        │  (Anthropic  │       │  & Codebases │
│   Storage    │        │  Compatible) │       │              │
└──────────────┘        └──────────────┘       └──────────────┘
```

### 5.2 Directory Structure

Follows the [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/latest/):
- **Config:** `$XDG_CONFIG_HOME/ask/` (defaults to `~/.config/ask/`)
- **Data:** `$XDG_DATA_HOME/ask/` (defaults to `~/.local/share/ask/`)

```
~/.config/ask/
└── config.json              # Global configuration (permissions: 600)

~/.local/share/ask/
├── history.json             # Conversation history
├── stats.json               # Usage statistics
├── executed_commands.log    # Command execution log
├── templates/               # User templates
│   ├── sap-transport.yaml
│   ├── docker-optimize.yaml
│   └── custom-template.yaml
├── saved/                   # Saved responses
│   ├── git-cheatsheet.json
│   └── docker-networks.json
└── kb/                      # Knowledge bases (v3.0+ extra)
    ├── baton/
    │   ├── index.db
    │   └── config.json
    └── sap-notes/
```

### 5.3 Configuration File Format

Stored at `~/.config/ask/config.json` with file permissions `600`.
API keys can also be set via environment variables (e.g. `ASK_ZAI_API_KEY`) which take precedence over the config file.

```json
{
  "default_provider": "zai",
  "providers": {
    "zai": {
      "api_key": "",
      "base_url": "https://api.z.ai/api/anthropic",
      "default_model": "glm-5",
      "models": ["glm-5", "glm-4.7", "glm-4.7-flash"],
      "fast_model": "glm-4.7-flash",
      "smart_model": "glm-5"
    },
    "anthropic": {
      "api_key": "",
      "default_model": "claude-sonnet-4-6",
      "models": ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5"],
      "fast_model": "claude-haiku-4-5",
      "smart_model": "claude-opus-4-6"
    },
    "openai": {
      "api_key": "",
      "default_model": "gpt-4o-mini",
      "models": ["gpt-4o", "gpt-4o-mini", "o1"],
      "fast_model": "gpt-4o-mini",
      "smart_model": "o1"
    },
    "google": {
      "api_key": "",
      "default_model": "gemini-2.5-flash",
      "models": ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-flash-lite"],
      "fast_model": "gemini-flash-lite",
      "smart_model": "gemini-2.5-pro"
    },
    "ollama": {
      "base_url": "http://localhost:11434",
      "default_model": "llama3.2",
      "models": ["llama3.2", "qwen2.5-coder", "mistral"],
      "fast_model": "llama3.2",
      "smart_model": "qwen2.5-coder"
    }
  },
  "defaults": {
    "max_tokens": 4096,
    "quick_max_tokens": 256,
    "history_ttl_hours": 1
  },
  "features": {
    "syntax_highlighting": true,
    "auto_save_sessions": true
  },
  "safety": {
    "require_confirmation": true,
    "log_executed_commands": true,
    "max_agent_steps": 10
  },
  "output": {
    "max_width": 120,
    "code_theme": "monokai"
  },
  "offline_fallback": {
    "enabled": false,
    "provider": "ollama"
  }
}
```

### 5.4 Dependencies

**Installation:** `pip install -e .` via `pyproject.toml`. Installs the `ask` command, replacing `~/bin/ask`.

**Core (always installed):**
- `anthropic` - API client (supports streaming, all providers via compatible APIs)
- `rich` - Terminal output, streaming display, syntax highlighting, markdown rendering
- `pyyaml` - Template parsing

**Standard (always installed, lightweight):**
- `pyperclip` - Clipboard integration (falls back gracefully if `xclip`/`xsel` not present)

**Optional extras (not installed by default):**
- `ask-cli[rag]` → `chromadb` + `sentence-transformers` - Knowledge base / RAG (v3.0+)

**Removed:**
- `prompt_toolkit` - No longer needed (interactive mode deferred)
- `pygments` - Covered by `rich`
- `sounddevice` + `whisper` - Voice input removed from roadmap

**Environment variable overrides for API keys:**
```bash
ASK_ZAI_API_KEY=...
ASK_ANTHROPIC_API_KEY=...
ASK_OPENAI_API_KEY=...
ASK_GOOGLE_API_KEY=...
```

---

## 6. Implementation Phases

### Phase 1: Foundation
**Goal:** Proper package structure, multi-provider, streaming, and conversation history. Fully replaces `~/bin/ask`.

**Features:**
- ✅ Python package with `pyproject.toml`, installs as `ask` via `pip install -e .`
- ✅ XDG-compliant config at `~/.config/ask/config.json`
- ✅ Multi-provider support (Z.ai, Anthropic, OpenAI, Google, Ollama) with `--provider`/`-p`
- ✅ `--fast` / `--smart` model shortcuts
- ✅ Streaming output via `rich.live` (always on, no flag)
- ✅ Conversation history (`-c/--continue`, `--clear`)
- ✅ Output formatting (`--markdown`, `--json`, `--code-only`, `--raw`, `--quick`)
- ✅ Basic template system (`--explain`, `--fix`, `--optimize`)
- ✅ Syntax highlighting via `rich` (always on, `--no-color` to disable)

**Deliverables:**
- Installable package replacing `~/bin/ask`
- Config file with API key management (env var + file)
- Basic test suite (pytest)

---

### Phase 2: Power Features
**Goal:** File context, command execution, and domain expertise modes

**Features:**
- ✅ File attachments (`-f <file>`, `-F <glob>`)
- ✅ Shell command generation with safety (`--cmd`, `--dry-run`)
- ✅ Specialized domain modes (`--sap`, `--docker`, `--sql`, `--git`, `--k8s`, `--aws`, `--security`, `--perf`)
- ✅ Save/recall responses (`--save`, `--recall`, `--list-saved`)
- ⏸ Interactive mode (`-i`) - deferred to v3.0, see section 4.6

**Deliverables:**
- Domain-specific prompt library
- Safety mechanisms for command execution with destructive command detection
- Enhanced error handling

---

### Phase 3: Advanced Capabilities
**Goal:** Agentic workflows, usage tracking, clipboard

**Features:**
- ✅ Terminal action agent (`--agent`, `--auto-approve`, `--agent-max-steps`)
- ✅ Usage statistics (`--stats`, `--stats-reset`)
- ✅ Clipboard integration (`--copy`, `--copy-code`)
- ⏸ Knowledge base / RAG (`--index`, `--kb`) - deferred to v3.0+ as optional extra

**Deliverables:**
- Agent execution framework with step-by-step approval
- Performance optimizations

---

### Phase 4: Polish & Quality of Life
**Goal:** Data management, encryption, model deprecation handling

**Features:**
- ✅ Data encryption at rest (`--enable-encryption`) - optional, disabled by default
- ✅ Model deprecation warnings and migration suggestions
- ✅ Offline fallback to Ollama when API unavailable
- ✅ Enhanced error messages with actionable suggestions
- ✅ Comprehensive documentation

**Deliverables:**
- Full documentation (README, USAGE, EXAMPLES)
- Packaging for broader distribution

---

## 7. Success Metrics

### 7.1 Usage Metrics
- **Daily Active Users:** Target 100+ users within 3 months
- **Queries per User:** Average 10+ queries/day
- **Feature Adoption:** 60% users try at least 3 different modes
- **Retention:** 70% weekly active users return after 1 month

### 7.2 Performance Metrics
- **Response Time:** < 2 seconds for 90% of queries
- **Success Rate:** > 95% queries return useful responses
- **Error Rate:** < 2% API or system errors

### 7.3 Quality Metrics
- **User Satisfaction:** > 4.5/5 average rating
- **Code Accuracy:** > 90% of generated commands work as expected
- **Time Savings:** Average 5+ minutes saved per query vs. web search

---

## 8. User Stories

### 8.1 Software Developer - Sarah
**Scenario:** Debugging a failing Docker container

```bash
# Get container logs
docker logs my-app 2>&1 | ask "why is this container failing?"

# Get specific fix suggestion
ask --docker --fix "why does my node app crash with ECONNREFUSED?"

# Generate and execute fix
ask --cmd "restart docker service"
```

**Outcome:** Sarah identifies and fixes the issue in 2 minutes instead of 15 minutes of Stack Overflow searching.

---

### 8.2 SAP Consultant - Emil
**Scenario:** Checking EWM queue status during cutover

```bash
# Quick SAP reference
ask --sap "transaction code to check warehouse task status"

# Analyze SAP log
ask -f /SAP/log/dev_w0 "are there any deadlocks in this log?"

# Continue conversation for deeper investigation
ask -c "what could cause this lock wait timeout?"
ask -c "how do I resolve it in EWM?"
```

**Outcome:** Emil quickly resolves a critical cutover issue without leaving the terminal or interrupting his workflow.

---

### 8.3 DevOps Engineer - Marcus
**Scenario:** Kubernetes pod troubleshooting

```bash
# Interactive troubleshooting session
ask -i --k8s

> My pod is in CrashLoopBackOff state
[Response with diagnostic steps]

> kubectl describe pod shows ImagePullBackOff
[Response with image registry debugging]

> how do I check if credentials are configured?
[Response with kubectl commands]
```

**Outcome:** Marcus diagnoses and fixes the issue through a guided conversation, learning best practices along the way.

---

### 8.4 System Administrator - Lisa
**Scenario:** Server cleanup and maintenance

```bash
# Agent-assisted cleanup
ask --agent "find old log files, check disk usage, and suggest cleanup plan"

[Agent creates plan]
[Lisa approves]
[Agent executes with confirmation at each step]

# Save the cleanup script for future use
ask --save monthly-cleanup "the cleanup commands we just used"
```

**Outcome:** Lisa automates a complex multi-step maintenance task with AI guidance and saves it for recurring use.

---

## 9. Security & Privacy

### 9.1 API Key Management
- Store API key in config file with restricted permissions (600)
- Support environment variable override: `ASK_API_KEY`
- Never log or display API key in output
- Warn if config file has insecure permissions

### 9.2 Command Execution Safety
- **Destructive Command Detection:** Flag rm, dd, mkfs, fdisk, etc.
- **Confirmation Required:** User must explicitly approve dangerous operations
- **Execution Logging:** All executed commands logged to `~/.local/share/ask/executed_commands.log`
- **Dry-Run Mode:** Test commands without execution
- **Timeout Protection:** Kill runaway commands after configurable timeout

### 9.3 Data Privacy
- **Local Storage:** All data stored locally in `~/.config/ask/` and `~/.local/share/ask/`
- **No External Tracking:** No analytics or tracking beyond Z.ai API calls
- **File Content:** Files sent to API are ephemeral, not stored by Z.ai
- **Conversation History:** Stored locally, user can clear anytime

### 9.4 Knowledge Base Security
- **Path Validation:** Prevent directory traversal attacks
- **File Size Limits:** Prevent memory exhaustion
- **Content Filtering:** Warn before indexing sensitive directories (.git, .env files)

---


### 9.5 Data Encryption (Optional)

**Priority:** Medium  
**Effort:** Low

**Description:**  
Optional at-rest encryption for sensitive data stored locally in `~/.local/share/ask/`.

**What Gets Encrypted:**
- Saved responses (`~/.local/share/ask/saved/`)
- Conversation history (`~/.local/share/ask/history.json`)
- Knowledge base indices (`~/.local/share/ask/kb/`)
- Session data (`~/.local/share/ask/sessions/`)

**What Does NOT Get Encrypted:**
- Configuration file (`~/.config/ask/config.json`) - stored with 600 permissions
- Statistics (`~/.local/share/ask/stats.json`)
- Executed commands log (already sanitized)

**Default Behavior:**
- **Encryption is DISABLED by default**
- Files stored in plain text for ease of access
- File permissions (600) provide basic OS-level protection
- User can enable encryption manually if needed

**Enabling Encryption:**
```bash
# Enable encryption (interactive)
ask --enable-encryption
This will encrypt all saved data in ~/.local/share/ask/
Enter encryption passphrase: ****
Confirm passphrase: ****
✓ Encryption enabled

Encrypting existing data...
✓ Encrypted 15 saved responses
✓ Encrypted conversation history
✓ Encrypted 2 knowledge bases

All new data will be encrypted automatically.

# Enable with passphrase file (non-interactive)
echo "my-secure-passphrase" > ~/.ask-passphrase
chmod 600 ~/.ask-passphrase
ask --enable-encryption --passphrase-file ~/.ask-passphrase
```

**Using Encrypted Data:**
```bash
# First use after restart prompts for passphrase
$ ask --recall sensitive-data
🔒 Encryption enabled. Enter passphrase: ****
[Displays saved response...]

# Passphrase cached for session
$ ask --recall another-item
[No prompt - uses cached passphrase...]

# Clear cached passphrase
ask --lock
✓ Passphrase cleared. You'll be prompted on next encrypted access.
```

**Disabling Encryption:**
```bash
# Decrypt all data and disable
ask --disable-encryption
🔒 Enter current passphrase: ****

Decrypting data...
✓ Decrypted 15 saved responses
✓ Decrypted conversation history
✓ Encryption disabled

Data is now stored in plain text.
```

**Implementation Details:**
```python
# Uses cryptography library with Fernet (AES-128)
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2

class EncryptionManager:
    def __init__(self, passphrase=None):
        self.passphrase = passphrase
        self.cipher = None
        
    def derive_key(self, passphrase, salt):
        """Derive encryption key from passphrase"""
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000
        )
        return base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
    
    def encrypt_file(self, filepath):
        """Encrypt a file in place"""
        with open(filepath, 'rb') as f:
            data = f.read()
        
        encrypted = self.cipher.encrypt(data)
        
        with open(filepath + '.enc', 'wb') as f:
            f.write(encrypted)
        
        os.remove(filepath)
        os.rename(filepath + '.enc', filepath)
```

**Storage Format:**
```json
{
  "encryption": {
    "enabled": true,
    "algorithm": "Fernet-AES128",
    "salt": "base64-encoded-salt",
    "kdf": "PBKDF2-SHA256",
    "iterations": 100000
  }
}
```

**Security Considerations:**
- Passphrase never stored on disk
- Salt generated randomly per installation
- PBKDF2 with 100,000 iterations prevents brute force
- Encrypted files have .enc suffix (transparent to user)
- Passphrase cached in memory for session convenience

**Warnings Displayed to User:**
```bash
⚠️  Important Security Notes:
• Encryption protects data at rest on disk
• API communication already uses HTTPS/TLS
• Passphrase is never stored - if forgotten, data is unrecoverable
• Backup your passphrase securely
• Consider using a password manager
```

---

## 10. Error Handling

### 10.1 Network Errors
```bash
$ ask "test query"
❌ Error: Unable to connect to Z.ai API
   - Check your internet connection
   - Verify API endpoint: https://api.z.ai/api/anthropic
   - Check API key in ~/.config/ask/config.json

Retry? [y/N]:
```

### 10.2 API Errors
```bash
$ ask "very long query..."
❌ Error: Token limit exceeded (1500/1024 tokens)
   Try:
   - Shorten your query
   - Use --max-tokens 2048
   - Split into multiple queries

Would you like to retry with increased token limit? [y/N]:
```

### 10.3 File Errors
```bash
$ ask -f nonexistent.log "analyze this"
❌ Error: File not found: nonexistent.log
   - Check file path is correct
   - Verify file permissions

$ ask -f hugefile.log "analyze this"
⚠️  Warning: File size (150 MB) exceeds limit (100 MB)
   Options:
   - Use --max-file-size 200M
   - Process file in chunks: tail -n 1000 hugefile.log | ask "analyze"
```

### 10.4 Agent Errors
```bash
$ ask --agent "complex task"
Step 3/10: Executing: docker stop $(docker ps -q)
❌ Error: Permission denied

Agent paused. Options:
  1. Skip this step
  2. Retry with sudo
  3. Abort agent execution

Choice [1-3]:
```

---

## 11. Testing Strategy

### 11.1 Unit Tests
**Coverage Target:** > 80%

**Test Areas:**
- CLI argument parsing
- Input/output formatting
- Template rendering
- File handling
- API client mocking

**Framework:** `pytest`

### 11.2 Integration Tests
**Test Scenarios:**
- End-to-end query execution
- Multi-turn conversations
- File attachment handling
- Agent workflow execution
- Knowledge base indexing/querying

### 11.3 Safety Tests
**Critical Tests:**
- Destructive command detection
- Command execution confirmation
- File path validation
- Token limit enforcement
- API error handling

### 11.4 Performance Tests
**Benchmarks:**
- Query response time < 2s (p90)
- File indexing speed
- Memory usage with large files
- Concurrent query handling

---

## 12. Documentation

### 12.1 User Documentation

**README.md:**
- Quick start guide
- Installation instructions
- Basic usage examples
- Feature overview

**USAGE.md:**
- Comprehensive flag reference
- Advanced usage patterns
- Template creation guide
- Configuration options

**EXAMPLES.md:**
- Real-world use cases by role
- Integration with existing workflows
- Best practices and tips

### 12.2 Developer Documentation

**ARCHITECTURE.md:**
- System design overview
- Module descriptions
- Data flow diagrams
- Extension points

**CONTRIBUTING.md:**
- Development setup
- Coding standards
- Pull request process
- Testing requirements

**API.md:**
- Internal API documentation
- Plugin system (future)
- Custom template format

---

## 13. Future Enhancements (v3.0+)

### 13.1 Plugin System
- Allow community-contributed plugins
- Plugin registry
- Easy installation: `ask --install-plugin <name>`

### 13.2 Team Collaboration
- Shared knowledge bases
- Collaborative sessions
- Shared saved responses

### 13.3 Integration with IDEs
- VSCode extension
- JetBrains plugin
- Vim/Neovim plugin

### 13.4 Advanced RAG
- Multi-modal indexing (images, diagrams)
- External documentation integration
- Auto-sync with Git repositories

### 13.5 Custom Model Training
- Fine-tune on company-specific data
- Domain-specific models
- Privacy-preserving training

### 13.6 Web Interface
- Browser-based version
- Share queries and responses
- Team analytics dashboard

---

## 14. Competitive Analysis

### 14.1 Existing Solutions

| Tool | Strengths | Weaknesses | Ask CLI Advantage |
|------|-----------|------------|-------------------|
| **GitHub Copilot CLI** | Great code generation | Expensive, limited to code | Multi-purpose, cheaper |
| **ChatGPT CLI** | Good general knowledge | No file/context, expensive | File support, specialized modes |
| **Warp AI** | Nice UI integration | Requires Warp terminal | Works in any terminal |
| **Aider** | Excellent code editing | Code-only, no general queries | Broader use cases |
| **Shell-GPT** | Simple, lightweight | Limited features | More features, better UX |

### 14.2 Differentiation

**Ask CLI Unique Value:**
1. **Cost-effective:** Uses affordable Z.ai subscription
2. **Domain expertise:** Built-in SAP, Docker, SQL modes
3. **Safety-first:** Smart command execution with confirmations
4. **Flexible input:** Text, pipes, files, voice
5. **Agentic capability:** Multi-step workflow automation
6. **Local-first:** Privacy-focused, local storage

---

## 15. Risks & Mitigation

### 15.1 Technical Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **API Changes** | High | Medium | Abstract API layer, version pinning |
| **Token Limits** | Medium | High | Smart chunking, context management |
| **Performance Issues** | Medium | Low | Caching, streaming, async operations |
| **Security Vulnerabilities** | High | Low | Code review, security audit, sandboxing |

### 15.2 Product Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **Low Adoption** | High | Medium | Focus on clear value prop, marketing |
| **Feature Creep** | Medium | High | Strict prioritization, MVP focus |
| **Support Burden** | Medium | Medium | Good docs, community forum |
| **Z.ai API Sunset** | High | Low | Multi-provider support (fallback) |

---

## 16. Open Questions

1. **Model Selection:**
   - ✅ **RESOLVED:** Should we support OpenAI/Anthropic native APIs as alternatives?
     - **YES** - Multi-provider support with Z.ai, Anthropic, OpenAI, Google Gemini, and Ollama
   - ✅ **RESOLVED:** How do we handle model deprecation?
     - Periodic checks of provider documentation pages, cache model status, warn users, suggest migrations

2. **Privacy:**
   - ✅ **RESOLVED:** Do we need end-to-end encryption for saved responses?
     - **Optional encryption** for data at rest (disabled by default)
     - User can enable with passphrase if needed
     - HTTPS/TLS already protects API communication
   - ✅ **RESOLVED:** Should we offer a fully offline mode with local models?
     - **YES** - Full Ollama support for completely offline operation
     - Privacy-first, zero API costs, air-gapped ready

3. **Monetization:**
   - Keep it free and open source?
   - Offer paid "pro" features (cloud sync, team features)?
   - *Status: OPEN - To be decided based on community feedback*

4. **Community:**
   - How do we build a community around this tool?
   - Template marketplace? Plugin ecosystem?
   - *Status: OPEN - To be decided post-launch*

5. **Enterprise:**
   - Should we build an enterprise version with:
     - SSO/LDAP integration
     - Audit logging
     - Admin controls
     - On-premise deployment
   - *Status: OPEN - Evaluate demand after v2.0 release*

---

## 17. Appendix

### 17.1 Command Reference (Quick Look)

```bash
# Basic usage
ask "your question"
command | ask "analyze this"

# Model selection
ask --fast "quick question"          # Fast model (no short form)
ask --smart "complex reasoning task" # Smart/reasoning mode (no short form)

# Conversation
ask "first question"
ask -c "follow-up question"          # Continue conversation
ask --clear                          # Clear history

# Output formats
ask --markdown "guide"               # Markdown output
ask --json "data"                    # JSON output
ask --code-only "function"           # Code only

# Templates
ask --explain "command"              # Explain command
ask --fix "error message"            # Fix error
ask --optimize "code/query"          # Optimization tips

# File handling
ask -f file.log "analyze"            # Single file
ask -F "*.py" "review"               # Multiple files

# Interactive mode - deferred to v3.0, use -c for follow-up questions instead

# Command execution
ask --cmd "task description"         # Generate command
ask --agent "complex workflow"       # Agent mode

# Specialized modes
ask --sap "question"                 # SAP mode
ask --docker "question"              # Docker mode
ask --sql "question"                 # SQL mode

# Knowledge base
ask --index ~/project --kb-name proj # Index directory
ask --kb proj "question"             # Query knowledge base

# Utilities
ask --save name "query"              # Save response
ask --recall name                    # Recall saved
ask --stats                          # Show statistics
ask --copy "query"                   # Copy to clipboard
```

### 17.2 Example Templates

**Template: SAP Transport**
```yaml
name: sap-transport
description: SAP transport request operations
prompt: |
  You are an SAP Basis expert specializing in transport management.
  
  Context:
  - System: {{system|default:ECC}}
  - Transport layer: {{transport_layer|default:SAP}}
  
  User question: {{query}}
  
  Provide:
  1. Relevant transaction codes (SE09, SE10, STMS, etc.)
  2. Step-by-step instructions
  3. Common pitfalls to avoid
```

**Template: Docker Optimize**
```yaml
name: docker-optimize
description: Optimize Dockerfiles and images
prompt: |
  You are a Docker expert focusing on optimization and best practices.
  
  Analyze the provided Dockerfile or docker-compose.yml.
  
  Provide:
  1. Multi-stage build opportunities
  2. Layer optimization suggestions
  3. Security improvements
  4. Size reduction techniques
  5. Caching optimization
  
  {{file_content}}
```

---

## 18. Changelog

### v2.0 (Planned - Q2 2026)
- Multi-model support
- Conversation history
- Template system
- File attachments
- Interactive mode
- Specialized domain modes
- Agent capabilities
- Knowledge base / RAG

### v1.0 (Current - Feb 2026)
- Basic question/answer
- Piped input support
- Z.ai integration
- Simple CLI interface

---

**Document Control**
- **Last Updated:** February 28, 2026
- **Next Review:** March 15, 2026
- **Owner:** Emil
- **Status:** Draft - Pending Review
