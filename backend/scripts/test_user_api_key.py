"""
Test script: verify that the backend accepts anthropic_api_key from the request body
and uses it to create per-request Anthropic clients.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import ResearchRequest
from main import get_anthropic_client

def test_research_request_accepts_anthropic_api_key():
    """ResearchRequest should accept an optional anthropic_api_key field."""
    req = ResearchRequest(
        person_name="Test Person",
        meeting_context="Test context",
        anthropic_api_key="sk-ant-test-key-123",
    )
    assert req.anthropic_api_key == "sk-ant-test-key-123", "Key should be stored on request"
    print("[PASS] ResearchRequest accepts anthropic_api_key")

def test_research_request_key_is_optional():
    """anthropic_api_key should default to None."""
    req = ResearchRequest(
        person_name="Test Person",
        meeting_context="Test context",
    )
    assert req.anthropic_api_key is None, "Key should default to None"
    print("[PASS] anthropic_api_key defaults to None")

def test_get_anthropic_client_with_user_key():
    """get_anthropic_client should use the user-provided key."""
    client = get_anthropic_client("sk-ant-user-provided-key")
    assert client is not None, "Client should be created"
    assert client.api_key == "sk-ant-user-provided-key", "Client should use user key"
    print("[PASS] get_anthropic_client uses user-provided key")

def test_get_anthropic_client_fallback_to_env():
    """get_anthropic_client should fall back to ANTHROPIC_API_KEY env var."""
    original = os.environ.get("ANTHROPIC_API_KEY")
    os.environ["ANTHROPIC_API_KEY"] = "sk-ant-env-fallback"
    try:
        client = get_anthropic_client(None)
        assert client is not None, "Client should be created from env"
        assert client.api_key == "sk-ant-env-fallback", "Client should use env key"
        print("[PASS] get_anthropic_client falls back to env ANTHROPIC_API_KEY")
    finally:
        if original:
            os.environ["ANTHROPIC_API_KEY"] = original
        else:
            os.environ.pop("ANTHROPIC_API_KEY", None)

def test_get_anthropic_client_no_key_raises():
    """get_anthropic_client should raise when no key is available."""
    original = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        from fastapi import HTTPException
        try:
            get_anthropic_client(None)
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 400, f"Expected 400, got {e.status_code}"
            print("[PASS] get_anthropic_client raises 400 when no key available")
    finally:
        if original:
            os.environ["ANTHROPIC_API_KEY"] = original

if __name__ == "__main__":
    print("=" * 60)
    print("Testing user-provided Anthropic API key support")
    print("=" * 60)
    test_research_request_accepts_anthropic_api_key()
    test_research_request_key_is_optional()
    test_get_anthropic_client_with_user_key()
    test_get_anthropic_client_fallback_to_env()
    test_get_anthropic_client_no_key_raises()
    print("=" * 60)
    print("All tests passed!")
