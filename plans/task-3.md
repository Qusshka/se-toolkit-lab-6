# Task 3: The System Agent - Implementation Plan

## Overview

Extend the Task 2 documentation agent with a `query_api` tool to query the deployed backend API. This enables answering:
- Static system facts (framework, ports, status codes)
- Data-dependent queries (item count, scores, analytics)
- Bug diagnosis (query API, get error, read source code)

## Implementation Plan

### 1. Environment Variables

Add support for reading backend configuration from environment variables:

| Variable | Purpose | Default |
|----------|---------|---------|
| `LMS_API_KEY` | Backend API authentication | Required |
| `AGENT_API_BASE_URL` | Backend base URL | `http://localhost:42002` |

These will be loaded from `.env.docker.secret` alongside the existing LLM config from `.env.agent.secret`.

### 2. Tool Schema: `query_api`

Define a new tool with the following schema:

```json
{
  "name": "query_api",
  "description": "Query the backend API to get data or check system behavior",
  "parameters": {
    "type": "object",
    "properties": {
      "method": {"type": "string", "description": "HTTP method (GET, POST, etc.)"},
      "path": {"type": "string", "description": "API path (e.g., /items/, /analytics/completion-rate)"},
      "body": {"type": "string", "description": "Optional JSON request body for POST/PUT"}
    },
    "required": ["method", "path"]
  }
}
```

### 3. Tool Implementation

Implement `query_api` function:
- Use `httpx` to make HTTP requests
- Add `Authorization: Bearer {LMS_API_KEY}` header
- Return JSON with `status_code` and `body`
- Handle errors gracefully (return error message, don't crash)

### 4. System Prompt Update

Update the system prompt to guide the LLM on tool selection:

```
You are a documentation and system assistant with three tools:
- list_files: List files in a directory
- read_file: Read file contents from the project repository
- query_api: Query the backend API to get live data or check system behavior

Tool selection guide:
- For wiki/documentation questions → use list_files and read_file
- For system facts (framework, ports) → use read_file on source code
- For data queries (item count, scores) → use query_api
- For bug diagnosis → use query_api first, then read_file to find the bug
```

### 5. Configuration Loading

Create `get_backend_config()` function:
- Load `LMS_API_KEY` from `.env.docker.secret` or environment
- Load `AGENT_API_BASE_URL` from environment (default: `http://localhost:42002`)
- Exit with error if `LMS_API_KEY` is missing

### 6. Benchmark Iteration Strategy

Run `uv run run_eval.py` and iterate:

1. **First run**: Identify which questions fail
2. **Common failures to fix**:
   - Agent doesn't use `query_api` for data questions → Improve tool description
   - Agent uses wrong HTTP method → Clarify in system prompt
   - Agent can't parse API response → Add better error handling
   - Answer doesn't contain expected keywords → Adjust LLM prompting

3. **Debugging approach**:
   - Check tool call traces in output
   - Verify API responses are being returned correctly
   - Ensure system prompt guides tool selection properly

## Initial Benchmark Results

**First Run:** 5/10 passed

**Failures:**
1. Question 2 (SSH): Missing 'source' field - agent answered but didn't include source reference
2. Question 6 (Status code without auth): Agent returned 200 instead of checking without auth header
3. Questions 7-10: Various issues with source extraction and tool selection

## Iteration Log

### Iteration 1: Fix source extraction
**Problem:** Agent wasn't including source field in output
**Solution:** 
- Updated system prompt to explicitly require "Source: wiki/filename.md" format
- Enhanced regex extraction to handle multiple patterns (wiki/, backend/, any .md file)
**Result:** Source field now properly extracted

### Iteration 2: Fix auth testing
**Problem:** Agent couldn't test unauthenticated API access
**Solution:**
- Added `auth` parameter to `query_api` tool (default: true)
- Updated tool description to mention setting auth=false for testing unauthenticated access
**Result:** Agent can now check 401/403 responses

### Iteration 3: Improve tool selection
**Problem:** LLM didn't always choose the right tool
**Solution:**
- Enhanced system prompt with explicit tool selection guide
- Added clearer descriptions to tool schemas
**Result:** Better tool selection for different question types

## Final Score

**10/10 PASSED** ✓

All local benchmark questions pass:
- ✓ Wiki lookups (branch protection, SSH connection)
- ✓ System facts (FastAPI framework, API routers)
- ✓ Data queries (item count via query_api)
- ✓ API behavior (401/403 status codes)
- ✓ Bug diagnosis (ZeroDivisionError, TypeError)
- ✓ Reasoning (request lifecycle, ETL idempotency)

## Test Results

Task 3 regression tests: 2/2 passed
- ✓ test_agent_uses_query_api_for_item_count
- ✓ test_agent_uses_read_file_for_framework_question
