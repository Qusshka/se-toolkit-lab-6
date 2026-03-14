# Agent Architecture

## Overview

This project implements an AI agent that answers questions by calling an LLM (Large Language Model). The agent is built as a CLI tool that takes a question as input and returns a structured JSON response.

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  CLI Argument   │────▶│   agent.py   │────▶│  LLM API     │────▶│  JSON Output │
│  (question)     │     │              │     │  (Qwen)      │     │  (stdout)    │
└─────────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
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
- Calls the LLM API
- Outputs a JSON response to stdout

**Usage:**
```bash
uv run agent.py "What does REST stand for?"
```

**Output:**
```json
{"answer": "Representational State Transfer.", "tool_calls": []}
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
- OpenAI-compatible API
- Strong tool calling capabilities (for future tasks)

**Model:** `qwen3-coder-plus`

### 4. HTTP Client

The agent uses `httpx` (synchronous client) to make HTTP POST requests to the LLM API.

**Request format:**
```
POST {LLM_API_BASE}/chat/completions
Authorization: Bearer {LLM_API_KEY}
Content-Type: application/json

{
  "model": "qwen3-coder-plus",
  "messages": [
    {"role": "user", "content": "Your question here"}
  ]
}
```

**Response format (OpenAI-compatible):**
```json
{
  "choices": [
    {
      "message": {
        "content": "The answer from the LLM"
      }
    }
  ]
}
```

### 5. Output Structure

The agent outputs a single JSON line to stdout:

```json
{
  "answer": "The LLM's response text",
  "tool_calls": []
}
```

- `answer`: The text response from the LLM (required)
- `tool_calls`: Empty array for Task 1 (will be populated in Task 2 when tools are added)

**Important:** All debug/progress output goes to stderr, only the JSON result goes to stdout.

## Error Handling

| Error | Behavior |
|-------|----------|
| Missing env vars | Print error to stderr, exit code 1 |
| API timeout (>60s) | Print error to stderr, exit code 1 |
| API connection error | Print error to stderr, exit code 1 |
| Invalid API response | Print error to stderr, exit code 1 |
| Success | Output JSON to stdout, exit code 0 |

## Running the Agent

### Prerequisites

1. Set up Qwen Code API on your VM (see [wiki/qwen.md](wiki/qwen.md))
2. Copy `.env.agent.example` to `.env.agent.secret`
3. Fill in `LLM_API_KEY`, `LLM_API_BASE`, and `LLM_MODEL`

### Test the Agent

```bash
# Test with a simple question
uv run agent.py "What is 2 + 2?"

# Expected output:
# {"answer": "2 + 2 = 4.", "tool_calls": []}
```

## Testing

Run the regression test:

```bash
# Run unit tests
uv run poe test-unit
```

The test verifies that:
- The agent outputs valid JSON
- The `answer` field is present and non-empty
- The `tool_calls` field is present and is an empty list

## Future Extensions (Tasks 2-3)

- **Task 2:** Add tool support (file operations, API queries)
- **Task 3:** Add agentic loop (plan → act → observe → repeat)

## File Structure

```
project-root/
├── agent.py              # Main CLI agent
├── AGENT.md              # This documentation
├── .env.agent.secret     # LLM configuration (gitignored)
├── .env.agent.example    # Example configuration
├── plans/
│   └── task-1.md         # Implementation plan
└── backend/tests/unit/
    └── test_agent_task1.py  # Regression test
```
