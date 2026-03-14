# Plan for Task 1: Call an LLM from Code

## LLM Provider

**Provider:** Qwen Code API (self-hosted on VM)
**Model:** `qwen3-coder-plus`

### Why this choice?
- 1000 free requests per day (enough for development and testing)
- Works from Russia
- OpenAI-compatible API (easy integration)
- Strong tool calling capabilities (needed for Task 2-3)

## Agent Architecture

### Input/Output Flow

```
CLI argument (question) 
    ↓
agent.py reads .env.agent.secret
    ↓
Build HTTP request to LLM_API_BASE/v1/chat/completions
    ↓
Send POST request with Authorization: Bearer LLM_API_KEY
    ↓
Parse JSON response from LLM
    ↓
Extract answer from response.choices[0].message.content
    ↓
Output: {"answer": "...", "tool_calls": []}
```

### Components

1. **Environment loading**
   - Use `os.environ` to read `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`
   - Load from `.env.agent.secret` using `python-dotenv` or manual parsing

2. **HTTP client**
   - Use `httpx` (already in project dependencies) for async/sync HTTP requests
   - POST to `{LLM_API_BASE}/chat/completions`
   - Headers: `Authorization: Bearer {LLM_API_KEY}`, `Content-Type: application/json`
   - Body: `{"model": LLM_MODEL, "messages": [{"role": "user", "content": question}]}`

3. **Response parsing**
   - Parse JSON response
   - Extract `choices[0].message.content` as the answer
   - Handle errors (timeout, invalid response, API errors)

4. **Output formatting**
   - Build output dict: `{"answer": answer_text, "tool_calls": []}`
   - Print to stdout as single JSON line
   - All debug logs to stderr

### Error Handling

- **Timeout:** 60 seconds max (use `httpx.Timeout(60.0)`)
- **API errors:** Print error to stderr, exit with code 1
- **Missing env vars:** Print helpful error to stderr, exit with code 1

### Testing Strategy

Create one regression test that:
1. Runs `agent.py "test question"` as subprocess
2. Parses stdout as JSON
3. Checks that `answer` field exists and is non-empty string
4. Checks that `tool_calls` field exists and is empty list

## Files to Create

1. `plans/task-1.md` — this plan
2. `agent.py` — main CLI agent
3. `.env.agent.secret` — environment config (copy from example, fill in values)
4. `AGENT.md` — documentation
5. `backend/tests/unit/test_agent_task1.py` — regression test

## Acceptance Criteria Checklist

- [ ] Plan exists before code
- [ ] `agent.py` outputs valid JSON with `answer` and `tool_calls`
- [ ] API key loaded from `.env.agent.secret` (not hardcoded)
- [ ] Debug output goes to stderr
- [ ] Exit code 0 on success
- [ ] 1 regression test passes
