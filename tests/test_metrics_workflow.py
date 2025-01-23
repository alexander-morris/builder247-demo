"""Tests for metrics workflow."""
import pytest
import json
import requests
from pathlib import Path
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

def test_performance_metrics_workflow(client):
    """Test complete performance metrics workflow."""
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Response")]
        )
        mock_client_class.return_value = mock_client
        
        # Start monitoring
        start_metrics = requests.get("http://localhost:8000/metrics").json()
        
        # Generate load
        conv_id = client.start_conversation("Performance Test")
        for _ in range(10):
            client.send_message("Test message")
        
        # Get updated metrics
        end_metrics = requests.get("http://localhost:8000/metrics").json()
        
        # Verify metrics
        assert end_metrics["request_count"] > start_metrics["request_count"]
        assert end_metrics["memory_usage"] >= start_metrics["memory_usage"]
        assert "error_count" in end_metrics
        assert "cpu_usage" in end_metrics
        
        # Check logs
        log_file = list(Path(client.storage_dir).glob("logs/prompt_log_*.jsonl"))[0]
        log_entries = [json.loads(line) for line in log_file.read_text().splitlines()]
        
        # Verify log entries
        assert len(log_entries) >= 10  # At least one entry per message
        for entry in log_entries:
            assert "timestamp" in entry
            assert "level" in entry
            assert "message" in entry

def test_monitoring_workflow(client):
    """Test monitoring workflow."""
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Response")]
        )
        mock_client_class.return_value = mock_client
        
        # Check initial metrics
        response = requests.get("http://localhost:8000/metrics")
        assert response.status_code == 200
        metrics = response.json()
        
        # Verify required metrics exist
        required_metrics = [
            "request_count",
            "error_count",
            "memory_usage",
            "cpu_usage",
            "response_time_avg",
            "token_count",
            "conversation_count"
        ]
        for metric in required_metrics:
            assert metric in metrics
        
        # Generate some activity
        for _ in range(3):
            client.start_conversation(f"Test {_}")
            client.send_message("Test message")
            client.save_conversation()
            client.clear_conversation()
        
        # Check updated metrics
        response = requests.get("http://localhost:8000/metrics")
        updated_metrics = response.json()
        
        # Verify metrics were updated
        assert updated_metrics["request_count"] > metrics["request_count"]
        assert updated_metrics["conversation_count"] > metrics["conversation_count"]
        assert updated_metrics["token_count"] > metrics["token_count"]

def test_alerting_workflow(client):
    """Test monitoring alerts workflow."""
    with patch('anthropic.Client') as mock_client_class:
        mock_client = MagicMock()
        
        # Test error rate alert
        error_response = MagicMock()
        error_response.status_code = 500
        mock_client.messages.create.side_effect = Exception("API Error")
        mock_client_class.return_value = mock_client
        
        # Generate errors
        for _ in range(10):
            try:
                client.send_message("Test message")
            except:
                pass
        
        # Check alerts
        response = requests.get("http://localhost:8000/alerts")
        assert response.status_code == 200
        alerts = response.json()
        
        # Verify error rate alert
        error_alerts = [a for a in alerts if a["type"] == "error_rate"]
        assert len(error_alerts) > 0
        assert error_alerts[0]["severity"] == "high"
        
        # Test resource usage alert
        large_data = ["x" * 1024 * 1024 for _ in range(100)]  # Allocate memory
        
        response = requests.get("http://localhost:8000/alerts")
        alerts = response.json()
        
        # Verify resource alert
        resource_alerts = [a for a in alerts if a["type"] == "resource_usage"]
        assert len(resource_alerts) > 0
        assert "memory" in resource_alerts[0]["message"].lower() 