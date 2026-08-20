"""Exception hierarchy for the LLM provider layer.

Every concrete LLMProvider (currently only OpenRouterProvider) must
raise one of these on failure — never a provider-specific exception —
so the agent graph and API layer can react to failure modes uniformly
regardless of which provider is behind the abstraction.
"""

from __future__ import annotations


class LLMProviderError(Exception):
    """Base class for all LLM provider errors."""


class LLMConnectionError(LLMProviderError):
    """Could not reach the LLM provider."""


class LLMTimeoutError(LLMProviderError):
    """The LLM provider did not respond within the configured timeout."""


class LLMAuthError(LLMProviderError):
    """The LLM provider rejected the configured credentials."""


class LLMRateLimitError(LLMProviderError):
    """The LLM provider's rate limit was exceeded."""


class LLMModelUnavailableError(LLMProviderError):
    """The configured model is not available (not found, deprecated, etc.)."""


class LLMResponseError(LLMProviderError):
    """The LLM provider returned a response that didn't match the expected shape."""
