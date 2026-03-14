# Agent Architecture

## Overview

This project implements an AI documentation and system agent that answers questions by calling an LLM (Large Language Model) with **tools**. The agent can read project files, list directories, and query the backend API to find accurate information from documentation and live system data.

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  CLI Argument   │────▶│   agent.py   │────▶│  LLM API     │────▶│  JSON Output │
│  (question)     │     │  (Agentic    │     │  (Qwen)      │     │  (stdout)    │
│                 │     │   Loop)      │     │              │     │              │
└─────────────────┘     └──────┬───────┘     └──────────────┘     └──────────────┘
                               │
                               ▼
                        ┌─────────────────────────┐
                        │ Tools:                  │
                        │ - read_file             │
                        │ - list_files            │
                        │ - query_api             │
                        └─────────────────────────┘
                               │
                               ▼
                        ┌─────────────────────────┐
                        │ .env.agent.secret       │
                        │ .env.docker.secret      │
                        └─────────────────────────┘
```

## Components

### 1. CLI Interface (`agent.py`)

The main entry point is a Python CLI script that:
- Accepts a single command-line argument (the question)
- Loads configuration from `.env.agent.secret` (LLM) and `.env.docker.secret` (backend)
- Runs an **agentic loop** with tool support
- Outputs a structured JSON response to stdout

**Usage:**
```bash
uv run agent.py "How many items are in the database?"
```

**Output:**
```json
{
  "answer": "There are 14 items in the database.",
  "source": "",
  "tool_calls": [
    {
      "tool": "query_api",
      "args": {"method": "GET", "path": "/items/"},
      "result": "{\"status_code\": 200, \"body\": \"[...]\"}"
    }
  ]
}
```

### 2. Configuration Files

#### `.env.agent.secret` (LLM Configuration)

| Variable | Description | Example |
|----------|-------------|---------|
| `LLM_API_KEY` | API key for LLM authentication | `my-secret-qwen-key` |
| `LLM_API_BASE` | Base URL of the LLM API | `http://localhost:42005/v1` |
| `LLM_MODEL` | Model name to use | `qwen3-coder-plus` |

#### `.env.docker.secret` (Backend Configuration)

| Variable | Description | Default |
|----------|-------------|---------|
| `LMS_API_KEY` | Backend API key for `query_api` authentication | `my-secret-api-key` |
| `AGENT_API_BASE_URL` | Base URL for backend API | `http://localhost:42002` |

**Important:** Both files are gitignored and should never be committed.

### 3. LLM Provider

**Provider:** Qwen Code API (self-hosted via qwen-code-oai-proxy)

**Why Qwen Code?**
- 1000 free requests per day
- Works from Russia
- OpenAI-compatible API with tool calling support
- Strong reasoning capabilities

**Model:** `qwen3-coder-plus`

### 4. Tools

The agent has three tools that the LLM can call:

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

#### `query_api`

Queries the backend API to get live data or check system behavior.

**Parameters:**
- `method` (string, required): HTTP method (GET, POST, PUT, DELETE)
- `path` (string, required): API path (e.g., `/items/`, `/analytics/completion-rate`)
- `body` (string, optional): JSON request body for POST/PUT requests
- `auth` (boolean, optional): Whether to include authentication header (default: true)

**Returns:** JSON string with `status_code` and `body`, or error message

**Authentication:**
- Uses `LMS_API_KEY` from `.env.docker.secret`
- Set `auth=false` to test unauthenticated access (e.g., checking 401 responses)

**Error Handling:**
- Timeout after 30 seconds
- Connection errors return descriptive messages
- HTTP errors are returned with status code

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
- Use `query_api` for data queries and API behavior checks
- Include source file paths in the final answer
- Call one tool at a time and wait for results

**Tool Selection Guide:**
- Wiki/documentation questions → `list_files` and `read_file` on `wiki/` files
- System facts (framework, ports, status codes) → `read_file` on source code
- Data queries (item count, scores, analytics) → `query_api`
- Bug diagnosis → `query_api` first to see the error, then `read_file` to find the bug

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
      "tool": "query_api",
      "args": {"method": "GET", "path": "/items/"},
      "result": "{\"status_code\": 200, \"body\": \"[...]\"}"
    }
  ]
}
```

- `answer` (string, required): The LLM's text response
- `source` (string, required): Reference to the source file (e.g., `wiki/git-workflow.md`)
- `tool_calls` (array, required): List of all tool calls made during the loop

**Important:** All debug/progress output goes to stderr, only the JSON result goes to stdout.

## Error Handling

| Error | Behavior |
|-------|----------|
| Missing env vars | Print error to stderr, exit code 1 |
| API timeout (>60s LLM, >30s backend) | Print error to stderr, exit code 1 |
| API connection error | Return error as tool result (no crash) |
| Path traversal attempt | Return error as tool result (no crash) |
| File not found | Return error as tool result |
| Max iterations (10) | Stop loop, return partial answer |
| Success | Output JSON to stdout, exit code 0 |

## Running the Agent

### Prerequisites

1. Set up Qwen Code API proxy (see `wiki/qwen.md`)
2. Copy `.env.agent.example` to `.env.agent.secret` and fill in LLM credentials
3. Copy `.env.docker.example` to `.env.docker.secret` and fill in backend credentials
4. Start the backend: `docker compose up -d`

### Test the Agent

```bash
# Ask about documentation
uv run agent.py "How do I protect a branch on GitHub?"

# Ask about system facts
uv run agent.py "What web framework does the backend use?"

# Query live data
uv run agent.py "How many items are in the database?"

# Check API behavior
uv run agent.py "What status code does /items/ return without auth?"
```

## Benchmark Evaluation

Run the local evaluation benchmark:

```bash
uv run run_eval.py
```

The benchmark tests 10 questions across all categories:
- Wiki lookups (branch protection, SSH connection)
- System facts (web framework, API routers)
- Data queries (item count)
- API behavior (status codes without auth)
- Bug diagnosis (ZeroDivisionError, TypeError)
- Reasoning (request lifecycle, ETL idempotency)

**Final Score:** 10/10 passed ✓

## Testing

Run the regression tests:

```bash
# Run Task 2 tests
uv run pytest test_agent_task2.py -v

# Run Task 3 tests
uv run pytest test_agent_task3.py -v

# Run all tests
uv run pytest test_agent_task*.py -v
```

Tests verify:
- Agent outputs valid JSON
- Correct tool usage for different question types
- Tool calls include `tool`, `args`, and `result` fields

## File Structure

```
project-root/
├── agent.py                  # Main CLI agent with agentic loop
├── AGENT.md                  # This documentation
├── .env.agent.secret         # LLM configuration (gitignored)
├── .env.docker.secret        # Backend configuration (gitignored)
├── plans/
│   ├── task-1.md             # Task 1 implementation plan
│   ├── task-2.md             # Task 2 implementation plan
│   └── task-3.md             # Task 3 implementation plan
├── test_agent_task1.py       # Task 1 regression test
├── test_agent_task2.py       # Task 2 regression tests
├── test_agent_task3.py       # Task 3 regression tests
├── run_eval.py               # Local evaluation runner
└── wiki/                     # Project documentation
└── backend/                  # FastAPI backend
```

## Lessons Learned

### Tool Design

1. **Explicit tool descriptions matter**: Initially, the LLM didn't use `query_api` for data questions. Adding clear guidance in the tool description ("Use for data queries like item count, scores") improved tool selection.

2. **Authentication flexibility**: The `auth` parameter in `query_api` was crucial for testing unauthenticated access. Without it, the agent couldn't answer questions about 401 responses.

3. **Source extraction**: The agent initially missed the `source` field. Adding explicit instructions in the system prompt ("Always include the source file path in this exact format: Source: wiki/filename.md") and improving the regex extraction fixed this.

### System Prompt Engineering

1. **Tool selection guide**: Providing explicit guidance on when to use each tool dramatically improved performance. The LLM now correctly chooses between wiki tools, file reading, and API queries.

2. **One tool at a time**: Limiting to one tool call per iteration prevents the LLM from making parallel calls that might conflict or waste iterations.

### Debugging

1. **stderr for debug output**: Keeping all debug output on stderr ensures clean JSON on stdout, which is critical for automated evaluation.

2. **Graceful error handling**: Returning errors as tool results (not crashing) allows the LLM to recover and try alternative approaches.

## Future Extensions

- Caching for frequently accessed files
- Support for streaming responses
- Multi-turn conversation support
- Enhanced source extraction with line numbers
