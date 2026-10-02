"""Unit tests for GroqClient and LLMService with mocked Groq SDK."""

from unittest.mock import MagicMock, patch
import pytest
import groq

from app.clients.groq_client import (
    BaseLLMClient,
    GroqClient,
    LLMAuthenticationError,
    LLMClientError,
    LLMEmptyResponseError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)
from app.services.llm_service import LLMService


# --- GroqClient Tests ---

def test_groq_client_init_missing_key() -> None:
    """Test that initializing Groq client without an API key raises LLMAuthenticationError."""
    client = GroqClient(api_key="")
    with pytest.raises(LLMAuthenticationError, match="Groq API key is not configured"):
        client._get_client()


def test_groq_client_success() -> None:
    """Test successful completion call via Groq SDK."""
    mock_choice = MagicMock()
    mock_choice.message.content = "  This week in Indore the weather was warm and sunny.  "
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch("app.clients.groq_client.Groq") as mock_groq_cls:
        mock_instance = MagicMock()
        mock_instance.chat.completions.create.return_value = mock_response
        mock_groq_cls.return_value = mock_instance

        client = GroqClient(api_key="gsk_test_key_123", model="llama-3.3-70b-versatile")
        result = client.generate_completion(
            system_prompt="System instructions",
            user_content="User content",
        )

        assert result == "This week in Indore the weather was warm and sunny."
        mock_instance.chat.completions.create.assert_called_once()
        args, kwargs = mock_instance.chat.completions.create.call_args
        assert kwargs["model"] == "llama-3.3-70b-versatile"
        assert kwargs["messages"][0]["content"] == "System instructions"
        assert kwargs["messages"][1]["content"] == "User content"


def test_groq_client_authentication_error() -> None:
    """Test that Groq AuthenticationError maps to LLMAuthenticationError."""
    with patch("app.clients.groq_client.Groq") as mock_groq_cls:
        mock_instance = MagicMock()
        mock_instance.chat.completions.create.side_effect = groq.AuthenticationError(
            message="Invalid API Key",
            response=MagicMock(status_code=401),
            body=None,
        )
        mock_groq_cls.return_value = mock_instance

        client = GroqClient(api_key="invalid_key")
        with pytest.raises(LLMAuthenticationError, match="Groq authentication failed"):
            client.generate_completion("system", "user")


def test_groq_client_timeout_error() -> None:
    """Test that Groq APITimeoutError maps to LLMTimeoutError."""
    with patch("app.clients.groq_client.Groq") as mock_groq_cls:
        mock_instance = MagicMock()
        mock_instance.chat.completions.create.side_effect = groq.APITimeoutError(
            request=MagicMock()
        )
        mock_groq_cls.return_value = mock_instance

        client = GroqClient(api_key="gsk_test_key", timeout=10.0)
        with pytest.raises(LLMTimeoutError, match="Groq request timed out"):
            client.generate_completion("system", "user")


def test_groq_client_rate_limit_error() -> None:
    """Test that Groq RateLimitError maps to LLMRateLimitError."""
    with patch("app.clients.groq_client.Groq") as mock_groq_cls:
        mock_instance = MagicMock()
        mock_instance.chat.completions.create.side_effect = groq.RateLimitError(
            message="Rate limit reached",
            response=MagicMock(status_code=429),
            body=None,
        )
        mock_groq_cls.return_value = mock_instance

        client = GroqClient(api_key="gsk_test_key")
        with pytest.raises(LLMRateLimitError, match="Groq rate limit exceeded"):
            client.generate_completion("system", "user")


def test_groq_client_service_unavailable() -> None:
    """Test that connection failure maps to LLMServiceUnavailableError."""
    with patch("app.clients.groq_client.Groq") as mock_groq_cls:
        mock_instance = MagicMock()
        mock_instance.chat.completions.create.side_effect = groq.APIConnectionError(
            request=MagicMock()
        )
        mock_groq_cls.return_value = mock_instance

        client = GroqClient(api_key="gsk_test_key")
        with pytest.raises(LLMServiceUnavailableError, match="Groq service unavailable"):
            client.generate_completion("system", "user")


def test_groq_client_empty_choices() -> None:
    """Test error when Groq returns empty choices array."""
    mock_response = MagicMock()
    mock_response.choices = []

    with patch("app.clients.groq_client.Groq") as mock_groq_cls:
        mock_instance = MagicMock()
        mock_instance.chat.completions.create.return_value = mock_response
        mock_groq_cls.return_value = mock_instance

        client = GroqClient(api_key="gsk_test_key")
        with pytest.raises(LLMEmptyResponseError, match="empty response choices"):
            client.generate_completion("system", "user")


def test_groq_client_empty_content_string() -> None:
    """Test error when Groq returns whitespace or empty string."""
    mock_choice = MagicMock()
    mock_choice.message.content = "   "
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch("app.clients.groq_client.Groq") as mock_groq_cls:
        mock_instance = MagicMock()
        mock_instance.chat.completions.create.return_value = mock_response
        mock_groq_cls.return_value = mock_instance

        client = GroqClient(api_key="gsk_test_key")
        with pytest.raises(LLMEmptyResponseError, match="empty text content"):
            client.generate_completion("system", "user")


# --- LLMService Tests ---

def test_llm_service_generate_summary_success() -> None:
    """Test LLMService returns sanitized summary from structured statistics."""
    mock_client = MagicMock(spec=BaseLLMClient)
    mock_client.generate_completion.return_value = (
        "```markdown\nThis week in Indore, average temperature was 28.4°C.\n```"
    )

    service = LLMService(client=mock_client)
    stats = {
        "average_temperature": 28.4,
        "minimum_temperature": 23.1,
        "maximum_temperature": 33.7,
        "average_humidity": 61.2,
        "total_precipitation": 12.4,
    }

    summary = service.generate_weather_summary("Indore", "week", stats)
    assert summary == "This week in Indore, average temperature was 28.4°C."
    mock_client.generate_completion.assert_called_once()


def test_llm_service_empty_stats_returns_none() -> None:
    """Test LLMService gracefully returns None when empty stats provided."""
    mock_client = MagicMock(spec=BaseLLMClient)
    service = LLMService(client=mock_client)

    result = service.generate_weather_summary("Indore", "week", {})
    assert result is None
    mock_client.generate_completion.assert_not_called()


def test_llm_service_handles_client_error_gracefully() -> None:
    """Test that LLMService catches client error and returns None instead of crashing."""
    mock_client = MagicMock(spec=BaseLLMClient)
    mock_client.generate_completion.side_effect = LLMTimeoutError("Request timed out")

    service = LLMService(client=mock_client)
    stats = {"average_temperature": 28.4}

    # Should not raise exception when raise_on_error is False
    result = service.generate_weather_summary("Indore", "week", stats, raise_on_error=False)
    assert result is None

    # Should raise when raise_on_error is True
    with pytest.raises(LLMTimeoutError):
        service.generate_weather_summary("Indore", "week", stats, raise_on_error=True)
