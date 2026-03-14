"""
Regression tests for Task 2: The Documentation Agent.

These tests verify that agent.py:
1. Uses tools (read_file, list_files) when answering questions
2. Returns proper JSON with answer, source, and tool_calls fields
"""

import json
import subprocess
import sys
from pathlib import Path


def test_agent_uses_read_file_for_merge_conflict():
    """Test that agent uses read_file tool when asked about merge conflicts."""
    project_root = Path(__file__).parent
    agent_path = project_root / "agent.py"

    result = subprocess.run(
        ["uv", "run", str(agent_path), "How do you resolve a merge conflict?"],
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

    # Check that git-related file was read
    for tc in tool_calls:
        if tc.get("tool") == "read_file":
            args: dict[str, str] = tc.get("args", {})
            path: str = args.get("path", "")
            assert "git" in path.lower(), f"Expected git-related file, got: {path}"


def test_agent_uses_list_files_for_wiki_question():
    """Test that agent uses list_files tool when asked about wiki files."""
    project_root = Path(__file__).parent
    agent_path = project_root / "agent.py"

    result = subprocess.run(
        ["uv", "run", str(agent_path), "What files are in the wiki?"],
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

    # Verify list_files was used
    tool_calls: list[dict[str, object]] = output["tool_calls"]
    assert isinstance(tool_calls, list), "'tool_calls' must be a list"
    assert len(tool_calls) > 0, "Expected at least one tool call"

    # Check that list_files was called
    tool_names: list[str] = [tc.get("tool", "") for tc in tool_calls]
    assert "list_files" in tool_names, (
        f"Expected 'list_files' in tool calls, got: {tool_names}"
    )

    # Check that wiki directory was listed
    for tc in tool_calls:
        if tc.get("tool") == "list_files":
            args: dict[str, str] = tc.get("args", {})
            path: str = args.get("path", "")
            assert path == "wiki", f"Expected 'wiki' path, got: {path}"


if __name__ == "__main__":
    print("Running test_agent_uses_read_file_for_merge_conflict...")
    test_agent_uses_read_file_for_merge_conflict()
    print("PASSED\n")

    print("Running test_agent_uses_list_files_for_wiki_question...")
    test_agent_uses_list_files_for_wiki_question()
    print("PASSED\n")

    print("All tests passed!")
