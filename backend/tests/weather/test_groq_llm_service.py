"""Unit tests for GroqClient and LLMService."""

from unittest.mock import MagicMock, patch
import pytest

from app.clients.groq_client import (
    GroqClient,
    LLMAuthenticationError,
    LLMClientError,
    LLMEmptyResponseError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)
from app.prompts.weather_prompts import (
    WEATHER_SUMMARY_SYSTEM_PROMPT,
    format_weather_summary_payload,
)
from app.services.llm_service import LLMService


def test_groq_client_unconfigured_api_key():
    """Test that GroqClient raises LLMAuthenticationError when no API key is provided."""
    with patch("app.clients.groq_client.settings") as mock_settings:
        mock_settings.groq_api_key = None
        client = GroqClient(api_key=None)
        with pytest.raises(LLMAuthenticationError) as exc_info:
            client.generate_completion("system prompt", "user content")
        assert "not configured" in str(exc_info.value).lower()


def test_groq_client_successful_completion():
    """Test successful completion call via Groq SDK."""
    mock_sdk_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Over the past 2 weeks, Indore recorded average temperatures of 28.5°C."
    mock_sdk_client.chat.completions.create.return_value.choices = [mock_choice]

    client = GroqClient(api_key="test-gsk-key", model="llama-3.3-70b-versatile", timeout=10.0)
    client._client = mock_sdk_client

    result = client.generate_completion(
        system_prompt="You are a meteorologist.",
        user_content="Indore stats data",
    )

    assert result == "Over the past 2 weeks, Indore recorded average temperatures of 28.5°C."
    mock_sdk_client.chat.completions.create.assert_called_once()
    kwargs = mock_sdk_client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "llama-3.3-70b-versatile"
    assert kwargs["temperature"] == 0.2
    assert kwargs["max_tokens"] == 512
    assert len(kwargs["messages"]) == 2
    assert kwargs["messages"][0]["role"] == "system"
    assert kwargs["messages"][1]["role"] == "user"


def test_groq_client_empty_response():
    """Test that an empty choice message raises LLMEmptyResponseError."""
    mock_sdk_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "   "
    mock_sdk_client.chat.completions.create.return_value.choices = [mock_choice]

    client = GroqClient(api_key="test-gsk-key")
    client._client = mock_sdk_client

    with pytest.raises(LLMEmptyResponseError):
        client.generate_completion("system", "user")


def test_groq_client_rate_limit_error():
    """Test mapping of rate limit errors."""
    mock_sdk_client = MagicMock()
    try:
        from groq import RateLimitError
        mock_sdk_client.chat.completions.create.side_effect = RateLimitError(
            message="Rate limit reached", response=MagicMock(status_code=429), body=None
        )
    except ImportError:
        mock_sdk_client.chat.completions.create.side_effect = Exception("Rate limit reached 429")

    client = GroqClient(api_key="test-gsk-key")
    client._client = mock_sdk_client

    with pytest.raises(LLMRateLimitError):
        client.generate_completion("system", "user")


def test_groq_client_timeout_error():
    """Test mapping of timeout errors."""
    mock_sdk_client = MagicMock()
    try:
        from groq import APITimeoutError
        mock_sdk_client.chat.completions.create.side_effect = APITimeoutError(request=MagicMock())
    except ImportError:
        mock_sdk_client.chat.completions.create.side_effect = TimeoutError("Request timed out")

    client = GroqClient(api_key="test-gsk-key")
    client._client = mock_sdk_client

    with pytest.raises(LLMTimeoutError):
        client.generate_completion("system", "user")


def test_groq_client_auth_error():
    """Test mapping of authentication errors from SDK."""
    mock_sdk_client = MagicMock()
    try:
        from groq import AuthenticationError
        mock_sdk_client.chat.completions.create.side_effect = AuthenticationError(
            message="Invalid API Key", response=MagicMock(status_code=401), body=None
        )
    except ImportError:
        mock_sdk_client.chat.completions.create.side_effect = Exception("Invalid API Key 401")

    client = GroqClient(api_key="test-gsk-key")
    client._client = mock_sdk_client

    with pytest.raises(LLMAuthenticationError):
        client.generate_completion("system", "user")


def test_llm_service_clean_output():
    """Test that LLMService cleans markdown artifacts and quotes from LLM outputs."""
    assert LLMService._clean_llm_output("```markdown\nHello world\n```") == "Hello world"
    assert LLMService._clean_llm_output("```text\nIndore temperature\n```") == "Indore temperature"
    assert LLMService._clean_llm_output('"A warm period in Bhopal."') == "A warm period in Bhopal."
    assert LLMService._clean_llm_output("'Temperatures averaged 26C.'") == "Temperatures averaged 26C."
    assert LLMService._clean_llm_output("   Normal text here   ") == "Normal text here"
    assert LLMService._clean_llm_output("") == ""


def test_llm_service_generate_weather_summary_success():
    """Test LLMService orchestrating prompt creation and client call."""
    mock_client = MagicMock()
    mock_client.generate_completion.return_value = (
        "Over the past 2 weeks in Indore, temperatures averaged 28.1°C with steady daytime heat."
    )

    service = LLMService(client=mock_client)
    sample_stats = {
        "overall_average_temperature_celsius": 28.1,
        "daily_records": [
            {"date": "2026-09-19", "average_temperature_celsius": 28.0, "status": "Available"},
            {"date": "2026-09-20", "average_temperature_celsius": 28.2, "status": "Available"},
        ],
    }

    summary = service.generate_weather_summary(
        city="Indore",
        period="week",
        duration=2,
        statistics=sample_stats,
    )

    assert summary == "Over the past 2 weeks in Indore, temperatures averaged 28.1°C with steady daytime heat."
    mock_client.generate_completion.assert_called_once()
    call_kwargs = mock_client.generate_completion.call_args.kwargs
    assert call_kwargs["system_prompt"] == WEATHER_SUMMARY_SYSTEM_PROMPT
    assert '"city": "Indore"' in call_kwargs["user_content"]
    assert '"period": "week"' in call_kwargs["user_content"]
    assert '"duration": 2' in call_kwargs["user_content"]


def test_llm_service_graceful_fallback_on_error():
    """Test that LLMService returns None without crashing when raise_on_error=False."""
    mock_client = MagicMock()
    mock_client.generate_completion.side_effect = LLMClientError("Provider unreachable")

    service = LLMService(client=mock_client)
    summary = service.generate_weather_summary(
        city="Indore",
        period="week",
        duration=1,
        statistics={"average_temperature_celsius": 27.5},
        raise_on_error=False,
    )

    assert summary is None


def test_llm_service_raises_on_error_when_requested():
    """Test that LLMService raises exception when raise_on_error=True."""
    mock_client = MagicMock()
    mock_client.generate_completion.side_effect = LLMClientError("Provider unreachable")

    service = LLMService(client=mock_client)
    with pytest.raises(LLMClientError):
        service.generate_weather_summary(
            city="Indore",
            period="week",
            duration=1,
            statistics={"average_temperature_celsius": 27.5},
            raise_on_error=True,
        )


def test_format_weather_summary_payload():
    """Test format_weather_summary_payload creates structured, injection-safe JSON."""
    payload = format_weather_summary_payload(
        city="Bhopal",
        period="month",
        duration=3,
        statistics={
            "overall_average_temperature_celsius": 26.8,
            "monthly_averages": [
                {"month": "July 2026", "average_temperature_celsius": 27.1, "coverage_percentage": 100.0},
                {"month": "August 2026", "average_temperature_celsius": 26.5, "coverage_percentage": 100.0},
                {"month": "September 2026", "average_temperature_celsius": 26.8, "coverage_percentage": 100.0},
            ],
            "data_coverage_percentage": 100.0,
        },
    )

    assert "Bhopal" in payload
    assert "3" in payload
    assert "26.8" in payload
    assert "July 2026" in payload
    assert "August 2026" in payload
    assert "September 2026" in payload
    assert "Calculated Historical Weather Statistics" in payload


def test_llm_service_generate_current_weather_summary_success():
    """Test LLMService generating professional current weather summary."""
    mock_client = MagicMock()
    mock_client.generate_completion.return_value = (
        "Indore is currently experiencing clear weather with a temperature of 32°C. "
        "The feels-like temperature is 31°C, with humidity at 27% and winds around 12.8 km/h. "
        "Overall, conditions are warm and dry, with no significant weather concerns based on the current observations."
    )

    service = LLMService(client=mock_client)
    sample_weather = {
        "city": "Indore",
        "resolved_address": "Indore, Madhya Pradesh, India",
        "temperature": 32.0,
        "feels_like": 31.0,
        "condition": "Clear",
        "humidity": 27,
        "wind_speed": 12.8,
        "cloud_cover": 18,
        "uv_index": 1.8,
        "visibility": 19.0,
        "precipitation": 0.0,
        "observed_at": "2026-10-03T16:45:00",
    }

    summary = service.generate_current_weather_summary("Indore", sample_weather)
    assert summary is not None
    assert "clear weather with a temperature of 32°C" in summary
    mock_client.generate_completion.assert_called_once()
    call_kwargs = mock_client.generate_completion.call_args.kwargs
    assert '"city": "Indore"' in call_kwargs["user_content"]
    assert '"temperature_celsius": 32.0' in call_kwargs["user_content"]


def test_llm_service_generate_current_weather_summary_failure_graceful():
    """Test LLMService returns None without raising when raise_on_error=False."""
    mock_client = MagicMock()
    mock_client.generate_completion.side_effect = LLMClientError("Connection refused")

    service = LLMService(client=mock_client)
    summary = service.generate_current_weather_summary("Indore", {"temperature": 28.0}, raise_on_error=False)
    assert summary is None


def test_format_current_weather_payload_omits_missing_fields():
    """Test that format_current_weather_payload only includes available fields."""
    from app.prompts.weather_prompts import format_current_weather_payload

    payload = format_current_weather_payload(
        city="Bhopal",
        weather_data={
            "temperature": 29.0,
            "feels_like": 30.5,
            "condition": "Partly Cloudy",
            "humidity": 65,
            "wind_speed": 10.0,
        },
    )

    assert "Bhopal" in payload
    assert "29.0" in payload
    assert "cloud_cover" not in payload
    assert "uv_index" not in payload
    assert "visibility" not in payload

