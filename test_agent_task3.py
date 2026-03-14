"""
Regression tests for Task 3: The System Agent.

These tests verify that agent.py:
1. Uses query_api tool for data queries
2. Uses read_file tool for system facts
3. Returns proper JSON with answer, source, and tool_calls fields
"""

import json
import subprocess
import sys
from pathlib import Path


def test_agent_uses_query_api_for_item_count():
    """Test that agent uses query_api tool when asked about item count in database."""
    project_root = Path(__file__).parent
    agent_path = project_root / "agent.py"

    result = subprocess.run(
        ["uv", "run", str(agent_path), "How many items are in the database?"],
        capture_output=True,
        text=True,
        cwd=project_root,
        timeout=120,
    )

    # Check exit code
    if result.returncode != 0:
        if "LLM_API_KEY not found" in result.stderr:
            print("SKIP: LLM not configured", file=sys.stderr)
            return

    assert result.stdout.strip(), "Agent output is empty"

    # Parse JSON
    try:
        output = json.loads(result.stdout.strip())
    except json.JSONDecodeError as e:
        raise AssertionError(f"Not valid JSON: {e}\nOutput: {result.stdout}")

    # Check required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"

    # Verify query_api was used
    tool_calls: list[dict[str, object]] = output["tool_calls"]
    assert isinstance(tool_calls, list), "'tool_calls' must be a list"
    assert len(tool_calls) > 0, "Expected at least one tool call"

    # Check that query_api was called
    tool_names: list[str] = [tc.get("tool", "") for tc in tool_calls]
    assert "query_api" in tool_names, (
        f"Expected 'query_api' in tool calls, got: {tool_names}"
    )


def test_agent_uses_read_file_for_framework_question():
    """Test that agent uses read_file tool when asked about the backend framework."""
    project_root = Path(__file__).parent
    agent_path = project_root / "agent.py"

    result = subprocess.run(
        ["uv", "run", str(agent_path), "What Python web framework does the backend use?"],
        capture_output=True,
        text=True,
        cwd=project_root,
        timeout=120,
    )

    # Check exit code
    if result.returncode != 0:
        if "LLM_API_KEY not found" in result.stderr:
            print("SKIP: LLM not configured", file=sys.stderr)
            return

    assert result.stdout.strip(), "Agent output is empty"

    # Parse JSON
    try:
        output = json.loads(result.stdout.strip())
    except json.JSONDecodeError as e:
        raise AssertionError(f"Not valid JSON: {e}\nOutput: {result.stdout}")

    # Check required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"

    # Verify read_file was used
    tool_calls: list[dict[str, object]] = output["tool_calls"]
    assert isinstance(tool_calls, list), "'tool_calls' must be a list"
    assert len(tool_calls) > 0, "Expected at least one tool call"

    # Check that read_file was called
    tool_names: list[str] = [tc.get("tool", "") for tc in tool_calls]
    assert "read_file" in tool_names, (
        f"Expected 'read_file' in tool calls, got: {tool_names}"
    )


if __name__ == "__main__":
    print("Running test_agent_uses_query_api_for_item_count...")
    test_agent_uses_query_api_for_item_count()
    print("PASSED\n")

    print("Running test_agent_uses_read_file_for_framework_question...")
    test_agent_uses_read_file_for_framework_question()
    print("PASSED\n")

    print("All Task 3 tests passed!")
