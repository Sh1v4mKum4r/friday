"""Ask cloud tool — lets the local LLM delegate hard questions to cloud providers.

When the local 3B model encounters something too complex (code generation,
detailed analysis, multi-step reasoning), it calls this tool to get help
from Claude, Gemini, or OpenAI.

This is the core of Friday's hybrid intelligence — fast local for simple
tasks, powerful cloud for complex ones, seamlessly.
"""

import httpx

name = "ask_cloud"
description = (
    "Ask a more powerful cloud AI (Claude, Gemini, or OpenAI) for help with complex tasks. "
    "Use this when you need: detailed code generation, multi-step analysis, long explanations, "
    "translation, or anything beyond your capabilities. The cloud AI's response is returned to you."
)

_FRIDAY_URL = "http://127.0.0.1:65535"


def run(question: str, provider: str = "") -> str:
    """Send a question to a cloud provider and return the response.

    Parameters
    ----------
    question:
        The full question or task to send to the cloud AI.
        Be specific — include all context the cloud AI needs.
    provider:
        Optional: 'claude', 'gemini', or 'openai'. If empty, Friday
        picks the best available (races cloud providers).
    """
    if not question or not question.strip():
        return "Error: question cannot be empty."

    # Map short names to provider names
    provider_map = {
        "claude": "claude-cli",
        "gemini": "gemini-cli",
        "openai": "openai",
    }

    force = provider_map.get(provider.lower().strip(), "") if provider else ""

    try:
        # Call Friday's own /chat endpoint with force_provider or race
        payload = {
            "message": question,
        }
        if force:
            payload["force_provider"] = force
        else:
            payload["race"] = True  # Race all cloud providers

        response = httpx.post(
            f"{_FRIDAY_URL}/chat",
            json=payload,
            timeout=120.0,
        )

        if response.status_code != 200:
            return f"Error: cloud request failed ({response.status_code})"

        data = response.json()
        cloud_response = data.get("response", "")
        cloud_provider = data.get("provider", "unknown")

        if not cloud_response:
            return "Error: cloud provider returned empty response."

        return f"[via {cloud_provider}] {cloud_response}"

    except httpx.TimeoutException:
        return "Error: cloud request timed out (120s). Try a shorter question."
    except httpx.ConnectError:
        return "Error: cannot connect to Friday backend. Is it running?"
    except Exception as e:
        return f"Error: {e}"
