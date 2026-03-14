# Plan for Task 2: The Documentation Agent

## Overview

Task 2 extends the agent from Task 1 with an **agentic loop** and **tools**. The agent can now:
1. Call tools (`read_file`, `list_files`) to interact with the project files
2. Loop: send question → LLM decides tool → execute tool → feed result back → repeat
3. Return a structured JSON with `answer`, `source`, and `tool_calls`

## Agentic Loop Architecture

```
Question ──▶ LLM (with tool definitions) ──▶ tool_calls?
                         │
                    ┌────┴────┐
                    │         │
                   yes       no
                    │         │
                    ▼         ▼
            Execute tools   Final answer
                    │         │
                    ▼         │
            Append results    │
            as tool messages  │
                    │         │
                    └────┬────┘
                         │
                         ▼
                   Loop (max 10 calls)
                         │
                         ▼
                   Output JSON
```

## Tool Definitions

### 1. `read_file`

**Purpose:** Read contents of a file from the project repository.

**Parameters:**
- `path` (string, required): Relative path from project root

**Returns:** File contents as string, or error message

**Security:**
- Reject paths containing `../` (path traversal)
- Reject absolute paths
- Only allow files within project root

**Schema (OpenAI function calling):**
```json
{
  "name": "read_file",
  "description": "Read the contents of a file",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {"type": "string", "description": "Relative path from project root"}
    },
    "required": ["path"]
  }
}
```

### 2. `list_files`

**Purpose:** List files and directories at a given path.

**Parameters:**
- `path` (string, required): Relative directory path from project root

**Returns:** Newline-separated listing of entries

**Security:**
- Reject paths containing `../`
- Only allow directories within project root

**Schema:**
```json
{
  "name": "list_files",
  "description": "List files in a directory",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {"type": "string", "description": "Relative directory path from project root"}
    },
    "required": ["path"]
  }
}
```

## System Prompt Strategy

The system prompt will instruct the LLM to:
1. Use `list_files` to discover wiki files when asked about documentation
2. Use `read_file` to read specific files and find answers
3. Include the source reference (file path + optional section anchor) in the final answer
4. Call tools step by step, not all at once

**Example system prompt:**
```
You are a documentation assistant. You have access to two tools:
- list_files: List files in a directory
- read_file: Read contents of a file

When answering questions about the project:
1. First use list_files to discover relevant files in the wiki/ directory
2. Then use read_file to read specific files and find the answer
3. Include the source file path in your answer (e.g., wiki/git-workflow.md#section)
4. Call one tool at a time and wait for results

Always provide accurate source references from the wiki.
```

## Implementation Steps

1. **Define tool schemas** — JSON schemas for OpenAI function calling
2. **Implement tool functions** — `read_file()` and `list_files()` with security checks
3. **Update LLM call** — Send tool definitions and handle tool_calls in response
4. **Implement agentic loop** — Loop until LLM returns final answer or max 10 calls
5. **Update output format** — Add `source` field, populate `tool_calls` with results
6. **Update tests** — Modify Task 1 test, add 2 new tests for tool calling

## Output Format

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "..."
    }
  ]
}
```

## Error Handling

- **Path traversal attempt:** Return error message, don't execute tool
- **File not found:** Return error message as tool result
- **LLM returns invalid tool call:** Log error, continue loop
- **Max iterations (10):** Stop loop, return partial answer

## Testing Strategy

**Test 1 (from Task 1):** Basic JSON output (update to include `source` field)

**Test 2:** Merge conflict question
- Question: `"How do you resolve a merge conflict?"`
- Expected: `read_file` in tool_calls, `wiki/git-workflow.md` in source

**Test 3:** Wiki listing question
- Question: `"What files are in the wiki?"`
- Expected: `list_files` in tool_calls

## Files to Modify/Create

1. `plans/task-2.md` — this plan
2. `agent.py` — add tools and agentic loop
3. `AGENT.md` — update documentation
4. `test_agent_task2.py` — add 2 regression tests (or update existing)

## Acceptance Criteria Checklist

- [ ] Plan exists before code
- [ ] `read_file` and `list_files` tool schemas defined
- [ ] Agentic loop executes tool calls and feeds results back
- [ ] `tool_calls` populated with tool, args, result
- [ ] `source` field identifies wiki section
- [ ] Security: no path traversal
- [ ] Max 10 tool calls per question
- [ ] 2 regression tests pass
- [ ] AGENT.md updated
