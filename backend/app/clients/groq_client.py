"""Groq LLM Client abstraction and error handling.

Architecture Rules:
- Abstract client interface allows future replacement or multi-provider routing.
- Low-level network/API exceptions are caught and wrapped in domain exceptions.
- API keys and timeouts are sourced dynamically from settings.
- Never hardcode API keys or model names.
"""

from abc import ABC, abstractmethod
from typing import Optional
import groq
from groq import Groq

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class LLMClientError(Exception):
    """Base exception for all LLM client failures."""
    pass


class LLMAuthenticationError(LLMClientError):
    """Raised when LLM API credentials are missing, rejected, or invalid."""
    pass


class LLMTimeoutError(LLMClientError):
    """Raised when LLM request times out."""
    pass


class LLMRateLimitError(LLMClientError):
    """Raised when LLM rate limit or quota is exceeded."""
    pass


class LLMServiceUnavailableError(LLMClientError):
    """Raised when LLM service is offline, unreachable, or returns 5xx."""
    pass


class LLMEmptyResponseError(LLMClientError):
    """Raised when LLM returns an empty or invalid payload."""
    pass


class BaseLLMClient(ABC):
    """Abstract interface defining LLM completion contract."""

    @abstractmethod
    def generate_completion(
        self,
        system_prompt: str,
        user_content: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate a text completion given system instructions and user content."""
        pass


class GroqClient(BaseLLMClient):
    """Production client for Groq Cloud API using official Groq Python SDK.
    
    Adheres to robust timeout, authentication, and error containment principles.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        temperature: Optional[float] = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.groq_api_key
        self.model = model if model is not None else settings.groq_model
        self.timeout = timeout if timeout is not None else settings.llm_timeout_seconds
        self.temperature = temperature if temperature is not None else settings.llm_temperature
        self._client: Optional[Groq] = None

    def _get_client(self) -> Groq:
        """Lazy-initialize and return the Groq SDK client instance."""
        if self._client is None:
            if not self.api_key or not self.api_key.strip():
                logger.warning("Groq API key is not configured.")
                raise LLMAuthenticationError(
                    "Groq API key is not configured. Set GROQ_API_KEY in your environment."
                )
            try:
                self._client = Groq(
                    api_key=self.api_key.strip(),
                    timeout=self.timeout,
                )
            except Exception as exc:
                logger.error("Failed to initialize Groq client: %s", exc)
                raise LLMClientError(f"Failed to initialize Groq client: {exc}") from exc
        return self._client

    def generate_completion(
        self,
        system_prompt: str,
        user_content: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = 512,
    ) -> str:
        """Call Groq chat completion API with robust error handling and response validation.
        
        Args:
            system_prompt: Fixed system instructions.
            user_content: Structured JSON or sanitized user message.
            temperature: Sampling temperature (defaults to settings.llm_temperature).
            max_tokens: Maximum tokens in generated completion.
            
        Returns:
            Non-empty, stripped summary text.
            
        Raises:
            LLMAuthenticationError: If API key is missing or unauthorized.
            LLMTimeoutError: If the request exceeds timeout bounds.
            LLMRateLimitError: If provider rate limit is hit.
            LLMServiceUnavailableError: If Groq service is down or network fails.
            LLMEmptyResponseError: If response text is empty or missing.
        """
        client = self._get_client()
        temp = temperature if temperature is not None else self.temperature

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        logger.info(
            "Dispatching LLM completion request to Groq (model='%s', timeout=%.1fs, temp=%.2f)",
            self.model,
            self.timeout,
            temp,
        )

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temp,
                max_tokens=max_tokens,
            )
        except groq.AuthenticationError as exc:
            logger.error("Groq authentication failed: %s", exc)
            raise LLMAuthenticationError(f"Groq authentication failed: {exc}") from exc
        except groq.APITimeoutError as exc:
            logger.error("Groq request timed out after %.1f seconds: %s", self.timeout, exc)
            raise LLMTimeoutError(f"Groq request timed out: {exc}") from exc
        except groq.RateLimitError as exc:
            logger.error("Groq rate limit exceeded: %s", exc)
            raise LLMRateLimitError(f"Groq rate limit exceeded: {exc}") from exc
        except (groq.APIConnectionError, groq.InternalServerError) as exc:
            logger.error("Groq service unavailable or network error: %s", exc)
            raise LLMServiceUnavailableError(f"Groq service unavailable: {exc}") from exc
        except groq.APIStatusError as exc:
            logger.error("Groq API returned error status %s: %s", exc.status_code, exc)
            raise LLMClientError(f"Groq API error (status {exc.status_code}): {exc}") from exc
        except Exception as exc:
            logger.exception("Unexpected error communicating with Groq: %s", exc)
            raise LLMClientError(f"Unexpected LLM error: {exc}") from exc

        # Response validation
        if not response.choices:
            logger.warning("Groq returned response without choices")
            raise LLMEmptyResponseError("Groq returned an empty response choices list.")

        choice = response.choices[0]
        content = choice.message.content if choice.message else None

        if not content or not content.strip():
            logger.warning("Groq returned empty content string")
            raise LLMEmptyResponseError("Groq returned an empty text content.")

        cleaned_text = content.strip()
        logger.info("Successfully received LLM completion (%d characters)", len(cleaned_text))
        return cleaned_text
