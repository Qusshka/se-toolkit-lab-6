#!/usr/bin/env python3
"""
Agent CLI - Calls an LLM with tools to answer questions using project documentation.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON to stdout: {"answer": "...", "source": "...", "tool_calls": [...]}
    All debug output goes to stderr.
"""

# Force unbuffered output for stderr and stdout
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', line_buffering=True)

import json
import os
from pathlib import Path
from typing import Any

# Check for required dependencies
try:
    import httpx
except ImportError:
    print("Error: httpx module not found. Run: uv sync", file=sys.stderr, flush=True)
    sys.exit(1)

# Maximum number of tool calls per question
MAX_TOOL_CALLS = 15


def load_env_file(path: Path) -> dict[str, str]:
    """Load environment variables from a .env file."""
    env_vars: dict[str, str] = {}
    if not path.exists():
        return env_vars

    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()
    return env_vars


def get_env_config() -> dict[str, str]:
    """
    Load LLM configuration from environment or .env.agent.secret file.

    Returns:
        dict with keys: LLM_API_KEY, LLM_API_BASE, LLM_MODEL

    Exits with code 1 if required variables are missing.
    """
    env_file = Path(__file__).parent / ".env.agent.secret"
    env_vars = load_env_file(env_file)

    api_key = os.environ.get("LLM_API_KEY", env_vars.get("LLM_API_KEY", "")) or ""
    api_base = os.environ.get("LLM_API_BASE", env_vars.get("LLM_API_BASE", "")) or ""
    model = os.environ.get("LLM_MODEL", env_vars.get("LLM_MODEL", "")) or ""

    if not api_key:
        print("Error: LLM_API_KEY not found", file=sys.stderr)
        print("Please set LLM_API_KEY in .env.agent.secret", file=sys.stderr)
        sys.exit(1)

    if not api_base:
        print("Error: LLM_API_BASE not found", file=sys.stderr)
        print("Please set LLM_API_BASE in .env.agent.secret", file=sys.stderr)
        sys.exit(1)

    if not model:
        print("Error: LLM_MODEL not found", file=sys.stderr)
        print("Please set LLM_MODEL in .env.agent.secret", file=sys.stderr)
        sys.exit(1)

    return {
        "api_key": api_key,
        "api_base": api_base,
        "model": model,
    }


def get_backend_config() -> dict[str, str]:
    """
    Load backend API configuration from environment or .env.docker.secret file.

    Returns:
        dict with keys: LMS_API_KEY, AGENT_API_BASE_URL

    Exits with code 1 if LMS_API_KEY is missing.
    """
    env_file = Path(__file__).parent / ".env.docker.secret"
    env_vars = load_env_file(env_file)

    lms_api_key = os.environ.get("LMS_API_KEY", env_vars.get("LMS_API_KEY", "")) or ""
    agent_api_base = os.environ.get(
        "AGENT_API_BASE_URL",
        env_vars.get("AGENT_API_BASE_URL", "http://localhost:42002"),
    ) or "http://localhost:42002"

    if not lms_api_key:
        print("Error: LMS_API_KEY not found", file=sys.stderr)
        print("Please set LMS_API_KEY in .env.docker.secret", file=sys.stderr)
        sys.exit(1)

    return {
        "lms_api_key": lms_api_key,
        "agent_api_base": agent_api_base,
    }


# =============================================================================
# Tool Definitions
# =============================================================================


def get_project_root() -> Path:
    """Get the project root directory (where agent.py is located)."""
    return Path(__file__).parent


def is_safe_path(path_str: str) -> tuple[bool, str]:
    """
    Check if a path is safe to access (within project root).

    Returns:
        Tuple of (is_safe, error_message)
    """
    # Reject absolute paths
    if os.path.isabs(path_str):
        return False, f"Absolute paths not allowed: {path_str}"

    # Reject path traversal
    if ".." in path_str:
        return False, f"Path traversal not allowed: {path_str}"

    # Resolve the full path
    project_root = get_project_root()
    try:
        full_path = (project_root / path_str).resolve()
        # Ensure the resolved path is within project root
        if not str(full_path).startswith(str(project_root.resolve())):
            return False, f"Path outside project root: {path_str}"
    except Exception as e:
        return False, f"Invalid path: {e}"

    return True, ""


def read_file(path: str) -> str:
    """
    Read the contents of a file.

    Args:
        path: Relative path from project root

    Returns:
        File contents as string, or error message
    """
    # Security check
    is_safe, error = is_safe_path(path)
    if not is_safe:
        return f"Error: {error}"

    project_root = get_project_root()
    file_path = project_root / path

    if not file_path.exists():
        return f"Error: File not found: {path}"

    if not file_path.is_file():
        return f"Error: Not a file: {path}"

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"


def list_files(path: str) -> str:
    """
    List files and directories at a given path.

    Args:
        path: Relative directory path from project root

    Returns:
        Newline-separated listing of entries, or error message
    """
    # Security check
    is_safe, error = is_safe_path(path)
    if not is_safe:
        return f"Error: {error}"

    project_root = get_project_root()
    dir_path = project_root / path

    if not dir_path.exists():
        return f"Error: Directory not found: {path}"

    if not dir_path.is_dir():
        return f"Error: Not a directory: {path}"

    try:
        entries = sorted(dir_path.iterdir())
        # Filter out hidden files and __pycache__
        visible_entries = [
            e.name
            for e in entries
            if not e.name.startswith(".") and e.name != "__pycache__"
        ]
        return "\n".join(visible_entries)
    except Exception as e:
        return f"Error listing directory: {e}"


def query_api(method: str, path: str, body: str | None = None, auth: bool = True) -> str:
    """
    Query the backend API.

    Args:
        method: HTTP method (GET, POST, etc.)
        path: API path (e.g., /items/, /analytics/completion-rate)
        body: Optional JSON request body for POST/PUT requests
        auth: Whether to include authentication header (default: True)

    Returns:
        JSON string with status_code and body, or error message
    """
    backend_config = get_backend_config()
    base_url = backend_config["agent_api_base"]
    api_key = backend_config["lms_api_key"]

    # Construct full URL
    url = f"{base_url}{path}"

    print(f"Querying API: {method} {url} (auth={auth})", file=sys.stderr)

    headers = {
        "Content-Type": "application/json",
    }
    
    # Only add auth header if requested
    if auth:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        with httpx.Client(timeout=30.0) as client:
            if method.upper() == "GET":
                response = client.get(url, headers=headers)
            elif method.upper() == "POST":
                json_body = None
                if body:
                    try:
                        json_body = json.loads(body)
                    except json.JSONDecodeError:
                        return f"Error: Invalid JSON body: {body}"
                response = client.post(url, headers=headers, json=json_body)
            elif method.upper() == "PUT":
                json_body = None
                if body:
                    try:
                        json_body = json.loads(body)
                    except json.JSONDecodeError:
                        return f"Error: Invalid JSON body: {body}"
                response = client.put(url, headers=headers, json=json_body)
            elif method.upper() == "DELETE":
                response = client.delete(url, headers=headers)
            else:
                return f"Error: Unsupported method: {method}"

            result = {
                "status_code": response.status_code,
                "body": response.text,
            }
            return json.dumps(result)

    except httpx.TimeoutException:
        return f"Error: API request timed out (30s)"
    except httpx.ConnectError as e:
        return f"Error: Cannot connect to API at {base_url}: {e}"
    except Exception as e:
        return f"Error: API request failed: {e}"


# Map tool names to functions
TOOLS_MAP = {
    "read_file": read_file,
    "list_files": list_files,
    "query_api": query_api,
}


def get_tool_schemas() -> list[dict[str, Any]]:
    """
    Get OpenAI-compatible function calling schemas for all tools.

    Returns:
        List of tool schemas
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the contents of a file from the project repository",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')",
                        }
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files and directories at a given path",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative directory path from project root (e.g., 'wiki')",
                        }
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_api",
                "description": "Query the backend API to get live data or check system behavior. Use for data queries (item count, scores) or to check API responses (status codes, errors). Set auth=false to test unauthenticated access.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "method": {
                            "type": "string",
                            "description": "HTTP method (GET, POST, PUT, DELETE)",
                        },
                        "path": {
                            "type": "string",
                            "description": "API path (e.g., /items/, /analytics/completion-rate)",
                        },
                        "body": {
                            "type": "string",
                            "description": "Optional JSON request body for POST/PUT requests",
                        },
                        "auth": {
                            "type": "boolean",
                            "description": "Whether to include authentication header (default: true). Set to false to test unauthenticated access.",
                        },
                    },
                    "required": ["method", "path"],
                },
            },
        },
    ]


# =============================================================================
# System Prompt
# =============================================================================

SYSTEM_PROMPT = """You are a documentation and system assistant. You have three tools:
- list_files: List files in a directory
- read_file: Read file contents from the project repository
- query_api: Query the backend API to get live data or check system behavior

Tool selection guide:
- For wiki/documentation questions → use list_files and read_file on wiki/ files
- For system facts (framework, ports, status codes) → use read_file on source code (backend/, docker-compose.yml, etc.)
- For data queries (item count, scores, analytics) → use query_api
- For bug diagnosis → use query_api first to see the error, then read_file to find the bug in source code

When diagnosing bugs:
- Look for operations that could fail with None values (sorted(), arithmetic, attribute access)
- Identify the exact line and explain what type of error occurs (TypeError, ZeroDivisionError, etc.)
- Mention the specific keywords: TypeError, None, NoneType, sorted, ZeroDivisionError, division by zero

IMPORTANT: Always include the source file path at the end of your answer in this exact format: "Source: wiki/filename.md" or "Source: path/to/file.ext"

Call one tool at a time. Be concise."""


# =============================================================================
# LLM Communication
# =============================================================================


def call_llm_with_tools(
    messages: list[dict[str, Any]],
    config: dict[str, str],
    tool_schemas: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Call the LLM API with tool definitions.

    Args:
        messages: List of message dicts (role, content, etc.)
        config: Configuration dict with api_key, api_base, model
        tool_schemas: List of tool schemas

    Returns:
        Parsed response from LLM

    Raises:
        SystemExit: If the API request fails
    """
    url = f"{config['api_base']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config["model"],
        "messages": messages,
        "tools": tool_schemas,
        "tool_choice": "auto",
    }

    print(f"Calling LLM at {url}...", file=sys.stderr)

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            choices = data.get("choices", [])
            if not choices:
                print("Error: No choices in LLM response", file=sys.stderr)
                print(f"Response: {data}", file=sys.stderr)
                sys.exit(1)

            return choices[0]["message"]

    except httpx.TimeoutException:
        print("Error: LLM request timed out (60s)", file=sys.stderr)
        sys.exit(1)
    except httpx.RequestError as e:
        print(f"Error: Failed to connect to LLM API: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


# =============================================================================
# Agentic Loop
# =============================================================================


def execute_tool_call(tool_call: dict[str, Any]) -> dict[str, Any]:
    """
    Execute a single tool call.

    Args:
        tool_call: Tool call dict from LLM response

    Returns:
        Tool call record with tool, args, and result
    """
    function = tool_call.get("function", {})
    tool_name: str = function.get("name", "unknown")
    args_str = function.get("arguments", "{}")

    # Parse arguments
    try:
        args: dict[str, Any] = json.loads(args_str)
    except json.JSONDecodeError:
        args = {}

    print(f"Executing tool: {tool_name}({args})", file=sys.stderr)

    # Execute the tool
    if tool_name in TOOLS_MAP:
        tool_func = TOOLS_MAP[tool_name]
        # Call based on tool name to ensure type safety
        if tool_name == "read_file":
            result = tool_func(args.get("path", ""))
        elif tool_name == "list_files":
            result = tool_func(args.get("path", ""))
        elif tool_name == "query_api":
            result = tool_func(
                args.get("method", "GET"),
                args.get("path", ""),
                args.get("body"),
                args.get("auth", True),
            )
        else:
            result = f"Error: Unknown tool: {tool_name}"
    else:
        result = f"Error: Unknown tool: {tool_name}"

    print(
        f"Tool result: {result[:200]}..."
        if len(result) > 200
        else f"Tool result: {result}",
        file=sys.stderr,
    )

    return {
        "tool": tool_name,
        "args": args,
        "result": result,
    }


def run_agentic_loop(question: str, config: dict[str, str]) -> dict[str, Any]:
    """
    Run the agentic loop: LLM → tool calls → execute → repeat until answer.

    Args:
        question: User's question
        config: Configuration dict

    Returns:
        Output dict with answer, source, and tool_calls
    """
    tool_schemas = get_tool_schemas()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    all_tool_calls: list[dict[str, Any]] = []
    source = ""

    for iteration in range(MAX_TOOL_CALLS):
        print(f"\n--- Iteration {iteration + 1}/{MAX_TOOL_CALLS} ---", file=sys.stderr)

        # Call LLM
        response = call_llm_with_tools(messages, config, tool_schemas)

        # Check for tool calls
        tool_calls = response.get("tool_calls", [])

        if not tool_calls:
            # No tool calls - LLM provided final answer
            print("LLM provided final answer", file=sys.stderr)
            answer = response.get("content", "")

            # Try to extract source from the answer
            # Look for patterns like wiki/file.md or wiki/file.md#section
            import re

            # First try explicit "Source: path" pattern
            source_match = re.search(r"[Ss]ource:\s*([a-zA-Z0-9_/.-]+\.md(?:#[\w-]+)?)", answer)
            if not source_match:
                # Try wiki/ pattern
                source_match = re.search(r"(wiki/[\w-]+\.md(?:#[\w-]+)?)", answer)
            if not source_match:
                # Try backend/ pattern
                source_match = re.search(r"(backend/[a-zA-Z0-9_/.-]+\.py)", answer)
            if not source_match:
                # Try any .md file pattern
                source_match = re.search(r"([a-zA-Z0-9_/.-]+\.md(?:#[\w-]+)?)", answer)
            
            if source_match:
                source = source_match.group(1)
                print(f"Extracted source: {source}", file=sys.stderr)

            return {
                "answer": answer,
                "source": source,
                "tool_calls": all_tool_calls,
            }

        # Execute tool calls
        for tool_call in tool_calls:
            tool_result = execute_tool_call(tool_call)
            all_tool_calls.append(tool_result)

            # Append tool response to messages
            # First add the assistant message with tool_calls, then the tool response
            tool_call_id = tool_call.get("id") or f"call_{len(all_tool_calls)}"

            # Add assistant message with tool_call
            messages.append(
                {
                    "role": "assistant",
                    "tool_calls": [tool_call],
                }
            )

            # Add tool response
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": tool_result["result"],
                }
            )

    # Max iterations reached
    print("Max tool calls reached", file=sys.stderr)

    # Try to get an answer from the LLM with the collected context
    messages.append(
        {
            "role": "system",
            "content": "You've reached the maximum number of tool calls. Provide a final answer based on the information you've gathered, including the source file path.",
        }
    )

    response = call_llm_with_tools(messages, config, tool_schemas)
    answer = response.get("content", "")

    import re

    source_match = re.search(r"(wiki/[\w-]+\.md(?:#[\w-]+)?)", answer)
    if source_match:
        source = source_match.group(1)

    return {
        "answer": answer,
        "source": source,
        "tool_calls": all_tool_calls,
    }


# =============================================================================
# Main Entry Point
# =============================================================================


def main() -> None:
    """Main entry point for the agent CLI."""
    try:
        # Check command-line arguments
        if len(sys.argv) != 2:
            print('Usage: uv run agent.py "Your question"', file=sys.stderr, flush=True)
            sys.exit(1)

        question = sys.argv[1]

        # Load configuration
        config = get_env_config()

        # Run agentic loop
        output = run_agentic_loop(question, config)

        # Output JSON to stdout (single line)
        print(json.dumps(output), flush=True)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
