"""
Regression test for Task 1: Call an LLM from Code.

This test verifies that agent.py:
1. Outputs valid JSON
2. Has 'answer' field (non-empty string)
3. Has 'tool_calls' field (empty list for Task 1)
"""

import json
import subprocess
import sys
from pathlib import Path


def test_agent_outputs_valid_json():
    """Test that agent.py outputs valid JSON with required fields."""
    # Path to agent.py - go up 3 levels from backend/tests/unit/
    project_root = Path(__file__).parent.parent.parent.parent
    agent_path = project_root / "agent.py"

    # Run agent with a simple test question
    # Note: This test requires a working LLM API configuration
    # If the API is not configured, this test will be skipped
    result = subprocess.run(
        ["uv", "run", str(agent_path), "What is 2 + 2?"],
        capture_output=True,
        text=True,
        cwd=project_root,
    )

    # Check exit code
    if result.returncode != 0:
        # If agent failed, check if it's due to missing configuration
        if (
            "LLM_API_KEY not found" in result.stderr
            or "LLM_API_BASE not found" in result.stderr
        ):
            print(
                "SKIP: LLM not configured. Set up .env.agent.secret first.",
                file=sys.stderr,
            )
            return  # Skip test gracefully

    # Check that stdout is not empty
    assert result.stdout.strip(), "Agent output is empty"

    # Parse JSON output
    try:
        output = json.loads(result.stdout.strip())
    except json.JSONDecodeError as e:
        raise AssertionError(
            f"Agent output is not valid JSON: {e}\nOutput: {result.stdout}"
        )

    # Check 'answer' field exists and is non-empty
    assert "answer" in output, "Missing 'answer' field in output"
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert len(output["answer"]) > 0, "'answer' is empty"

    # Check 'tool_calls' field exists and is empty list
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be a list"
    assert len(output["tool_calls"]) == 0, "'tool_calls' must be empty for Task 1"


if __name__ == "__main__":
    test_agent_outputs_valid_json()
    print("Test passed!")
