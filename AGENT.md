# Agent Architecture

## Overview

This project implements an AI documentation agent that answers questions by calling an LLM (Large Language Model) with **tools**. The agent can read project files and list directories to find accurate information from the project documentation.

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  CLI Argument   │────▶│   agent.py   │────▶│  LLM API     │────▶│  JSON Output │
│  (question)     │     │  (Agentic    │     │  (Qwen)      │     │  (stdout)    │
│                 │     │   Loop)      │     │              │     │              │
└─────────────────┘     └──────┬───────┘     └──────────────┘     └──────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │ Tools:       │
                        │ - read_file  │
                        │ - list_files │
                        └──────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │ .env.agent   │
                        │ .secret      │
                        └──────────────┘
```

## Components

### 1. CLI Interface (`agent.py`)

The main entry point is a Python CLI script that:
- Accepts a single command-line argument (the question)
- Loads configuration from `.env.agent.secret`
- Runs an **agentic loop** with tool support
- Outputs a structured JSON response to stdout

**Usage:**
```bash
uv run agent.py "What files are in the wiki?"
```

**Output:**
```json
{
  "answer": "The wiki directory contains...",
  "source": "wiki/git-workflow.md",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "file1.md\nfile2.md\n..."
    }
  ]
}
```

### 2. Configuration (`.env.agent.secret`)

The agent reads the following environment variables from `.env.agent.secret`:

| Variable | Description | Example |
|----------|-------------|---------|
| `LLM_API_KEY` | API key for authentication | `your-api-key` |
| `LLM_API_BASE` | Base URL of the LLM API | `http://192.168.1.100:8080/v1` |
| `LLM_MODEL` | Model name to use | `qwen3-coder-plus` |

**Important:** This file is gitignored (`.gitignore`) and should never be committed.

### 3. LLM Provider

**Provider:** Qwen Code API (self-hosted on VM)

**Why Qwen Code?**
- 1000 free requests per day
- Works from Russia
- OpenAI-compatible API with tool calling support
- Strong reasoning capabilities

**Model:** `qwen3-coder-plus`

### 4. Tools

The agent has two tools that the LLM can call:

#### `read_file`

Reads the contents of a file from the project repository.

**Parameters:**
- `path` (string, required): Relative path from project root

**Returns:** File contents as string, or error message

**Security:**
- Rejects absolute paths
- Rejects paths containing `../` (path traversal prevention)
- Only allows files within project root

#### `list_files`

Lists files and directories at a given path.

**Parameters:**
- `path` (string, required): Relative directory path from project root

**Returns:** Newline-separated listing of entries, or error message

**Security:**
- Same path validation as `read_file`
- Filters out hidden files (starting with `.`) and `__pycache__`

### 5. Agentic Loop

The agent implements an iterative loop:

```
1. Send question + system prompt to LLM (with tool definitions)
2. LLM responds with either:
   a. tool_calls → Execute tools, append results, go to step 1
   b. Final answer → Extract answer and source, output JSON, exit
3. Maximum 10 iterations (prevents infinite loops)
```

**Message Format:**
```python
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": question},
    # If tools are called:
    {"role": "assistant", "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "...", "content": "result"},
    # Loop continues...
]
```

### 6. System Prompt

The system prompt instructs the LLM to:
- Use `list_files` to discover relevant files in `wiki/`
- Use `read_file` to read specific files and find answers
- Include source file paths in the final answer
- Call one tool at a time and wait for results

**Example:**
```
You are a documentation assistant. You have two tools:
- list_files: List files in a directory
- read_file: Read file contents

To answer questions:
1. Use list_files to find relevant files in wiki/
2. Use read_file to read files and find answers
3. Include source path in your answer (e.g., wiki/git-workflow.md)

Call one tool at a time. Be concise.
```

### 7. Output Structure

The agent outputs a single JSON line to stdout:

```json
{
  "answer": "The answer from the LLM",
  "source": "wiki/git-workflow.md#section",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "file1.md\nfile2.md"
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "File contents..."
    }
  ]
}
```

- `answer` (string, required): The LLM's text response
- `source` (string, required): Reference to the wiki file (e.g., `wiki/git-workflow.md`)
- `tool_calls` (array, required): List of all tool calls made during the loop

**Important:** All debug/progress output goes to stderr, only the JSON result goes to stdout.

## Error Handling

| Error | Behavior |
|-------|----------|
| Missing env vars | Print error to stderr, exit code 1 |
| API timeout (>60s) | Print error to stderr, exit code 1 |
| API connection error | Print error to stderr, exit code 1 |
| Invalid API response | Print error to stderr, exit code 1 |
| Path traversal attempt | Return error as tool result (no crash) |
| File not found | Return error as tool result |
| Max iterations (10) | Stop loop, return partial answer |
| Success | Output JSON to stdout, exit code 0 |

## Running the Agent

### Prerequisites

1. Set up Qwen Code API on your VM (see [wiki/qwen.md](wiki/qwen.md))
2. Copy `.env.agent.example` to `.env.agent.secret`
3. Fill in `LLM_API_KEY`, `LLM_API_BASE`, and `LLM_MODEL`

### Test the Agent

```bash
# List wiki files
uv run agent.py "What files are in the wiki?"

# Ask about merge conflicts
uv run agent.py "How do you resolve a merge conflict?"

# Ask about git workflow
uv run agent.py "How do I create a pull request?"
```

## Testing

Run the regression tests:

```bash
# Run Task 2 tests
uv run pytest test_agent_task2.py -v

# Run all tests
uv run pytest test_agent_task1.py test_agent_task2.py -v
```

Tests verify:
- Agent outputs valid JSON
- `read_file` tool is used for documentation questions
- `list_files` tool is used for directory listing questions
- Tool calls include `tool`, `args`, and `result` fields

## File Structure

```
project-root/
├── agent.py              # Main CLI agent with agentic loop
├── AGENT.md              # This documentation
├── .env.agent.secret     # LLM configuration (gitignored)
├── .env.agent.example    # Example configuration
├── plans/
│   ├── task-1.md         # Task 1 implementation plan
│   └── task-2.md         # Task 2 implementation plan
├── test_agent_task1.py   # Task 1 regression test
├── test_agent_task2.py   # Task 2 regression tests
└── wiki/                 # Project documentation (agent reads from here)
    ├── git-workflow.md
    ├── git.md
    └── ...
```

## Future Extensions (Task 3)

- **Task 3:** Add more tools (API queries, code execution)
- Enhanced source extraction with section anchors
- Improved error recovery and retry logic
- Caching for frequently accessed files
