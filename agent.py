#!/usr/bin/env python3
"""
Agent CLI - Calls an LLM to answer questions.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON to stdout: {"answer": "...", "tool_calls": []}
    All debug output goes to stderr.
"""

import json
import os
import sys
from pathlib import Path

import httpx


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


def call_lllm(question: str, config: dict[str, str]) -> str:
    """
    Call the LLM API and get an answer.

    Args:
        question: The user's question
        config: Configuration dict with api_key, api_base, model

    Returns:
        The LLM's answer as a string

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
        "messages": [{"role": "user", "content": question}],
    }

    print(f"Calling LLM at {url}...", file=sys.stderr)

    try:
        # Use timeout of 60 seconds as per requirements
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            # Extract answer from response
            # OpenAI-compatible format: choices[0].message.content
            choices = data.get("choices", [])
            if not choices:
                print("Error: No choices in LLM response", file=sys.stderr)
                print(f"Response: {data}", file=sys.stderr)
                sys.exit(1)

            answer = choices[0].get("message", {}).get("content", "")
            if not answer:
                print("Error: Empty answer from LLM", file=sys.stderr)
                print(f"Response: {data}", file=sys.stderr)
                sys.exit(1)

            return answer

    except httpx.TimeoutException:
        print("Error: LLM request timed out (60s)", file=sys.stderr)
        sys.exit(1)
    except httpx.RequestError as e:
        print(f"Error: Failed to connect to LLM API: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main entry point for the agent CLI."""
    # Check command-line arguments
    if len(sys.argv) != 2:
        print('Usage: uv run agent.py "Your question"', file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    # Load configuration
    config = get_env_config()

    # Call LLM and get answer
    answer = call_lllm(question, config)

    # Build output structure
    output: dict[str, str | list[object]] = {
        "answer": answer,
        "tool_calls": [],
    }

    # Output JSON to stdout (single line)
    print(json.dumps(output))


if __name__ == "__main__":
    main()
