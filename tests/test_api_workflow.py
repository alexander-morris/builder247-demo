"""Tests for API workflow."""
import pytest
import requests
from unittest.mock import patch, MagicMock
from src.client import AnthropicClient

@pytest.fixture
def temp_storage(tmp_path):
    """Create temporary storage directory."""
    return str(tmp_path)

@pytest.fixture
def mock_env(monkeypatch, temp_storage):
    """Set up test environment variables."""
    monkeypatch.setenv("CLAUDE_API_KEY", "test-key")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("STORAGE_DIR", temp_storage)
    monkeypatch.setenv("MAX_RETRIES", "3")

@pytest.fixture
def client(mock_env, temp_storage):
    """Create a test client instance."""
    return AnthropicClient(storage_dir=temp_storage)

def test_api_interaction_workflow(client):
    """Test complete API interaction workflow."""
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="API Response")]
        )
        mock_client_class.return_value = mock_client
        
        # Test API endpoints
        endpoints = [
            ("/api/v1/conversation/start", {"title": "Test Conversation"}),
            ("/api/v1/message", {"message": "Test message"}),
            ("/api/v1/conversation/load", {"conversation_id": "test-id"}),
            ("/api/v1/conversation/save", {}),
            ("/api/v1/conversation/clear", {})
        ]
        
        for endpoint, payload in endpoints:
            response = requests.post(
                f"http://localhost:8000{endpoint}",
                json=payload
            )
            assert response.status_code == 200
            data = response.json()
            assert "error" not in data
            
            if "message" in payload:
                assert "response" in data
            elif "conversation_id" in payload:
                assert "messages" in data

def test_api_error_handling(client):
    """Test API error handling workflow."""
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        
        # Test invalid requests
        invalid_payloads = [
            ({}, 400),  # Missing required fields
            ({"invalid": "data"}, 400),  # Invalid payload
            ({"message": "x" * 100000}, 413)  # Message too long
        ]
        
        for payload, expected_status in invalid_payloads:
            response = requests.post(
                "http://localhost:8000/api/v1/message",
                json=payload
            )
            assert response.status_code == expected_status
            data = response.json()
            assert "error" in data
            
        # Test rate limiting
        for _ in range(60):  # Should hit rate limit
            response = requests.post(
                "http://localhost:8000/api/v1/message",
                json={"message": "test"}
            )
            if response.status_code == 429:
                break
        else:
            pytest.fail("Rate limit not enforced")

def test_api_authentication(client):
    """Test API authentication workflow."""
    # Test without auth token
    response = requests.post(
        "http://localhost:8000/api/v1/message",
        json={"message": "test"}
    )
    assert response.status_code == 401
    
    # Test with invalid auth token
    response = requests.post(
        "http://localhost:8000/api/v1/message",
        headers={"Authorization": "Bearer invalid-token"},
        json={"message": "test"}
    )
    assert response.status_code == 401
    
    # Test with valid auth token
    response = requests.post(
        "http://localhost:8000/api/v1/message",
        headers={"Authorization": "Bearer test-key"},
        json={"message": "test"}
    )
    assert response.status_code == 200 