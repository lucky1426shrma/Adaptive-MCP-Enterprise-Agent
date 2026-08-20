"""Validates, at startup, that the configured OpenRouter model is
explicitly free ($0 prompt and completion cost) — the project's
zero-cost requirement. Fails closed: if the model can't be confirmed
free, `validate_model_is_free` raises and the application does not
start with the agent enabled.

Does NOT hardcode any assumption about which models are currently
free — free-model availability changes over time. This calls
OpenRouter's public `/models` endpoint and checks CURRENT pricing for
the configured model every time the application starts, rather than
trusting a cached or hardcoded assumption.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

OPENROUTER_MODELS_PATH = "/models"


class ModelValidationError(Exception):
    """Raised when the configured OpenRouter model cannot be confirmed free."""


async def validate_model_is_free(
    model_id: str,
    api_key: Optional[str] = None,
    base_url: str = "https://openrouter.ai/api/v1",
    timeout_seconds: float = 15.0,
    max_retries: int = 3,
) -> None:
    if not model_id:
        raise ModelValidationError(
            "OPENROUTER_MODEL is not set. Configure a specific, explicitly-free OpenRouter model ID."
        )

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    last_error: Optional[Exception] = None
    data = None

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(
                base_url=base_url.rstrip("/"),
                headers=headers,
                timeout=timeout_seconds,
            ) as client:
                response = await client.get(OPENROUTER_MODELS_PATH)
                response.raise_for_status()
                data = response.json()
                break
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            last_error = exc
            if attempt < max_retries:
                logger.warning(
                    "openrouter_model_validation_retry",
                    extra={
                        "event": "openrouter_model_validation_retry",
                        "attempt": attempt,
                        "error": str(exc),
                    },
                )
                await asyncio.sleep(1.0 * attempt)
            else:
                logger.error(
                    "openrouter_model_validation_network_failed",
                    extra={
                        "event": "openrouter_model_validation_network_failed",
                        "error": str(exc),
                    },
                )

    if data is None:
        # If network failed after retries: if model ends with ':free', log warning and allow startup
        if model_id.endswith(":free"):
            logger.warning(
                "openrouter_model_validation_skipped_on_network_error",
                extra={
                    "event": "openrouter_model_validation_skipped_on_network_error",
                    "model": model_id,
                    "error": str(last_error),
                },
            )
            return
        raise ModelValidationError(
            f"Could not reach OpenRouter's /models endpoint to validate '{model_id}' is free: {last_error}"
        ) from last_error

    models = data.get("data", [])
    match = next((m for m in models if m.get("id") == model_id), None)

    if match is None:
        if model_id.endswith(":free"):
            logger.info(
                "openrouter_model_has_free_suffix",
                extra={"event": "openrouter_model_has_free_suffix", "model": model_id},
            )
            return
        raise ModelValidationError(
            f"OpenRouter model '{model_id}' was not found in the current model list. "
            "It may have been renamed or removed — check https://openrouter.ai/models "
            "and update OPENROUTER_MODEL."
        )

    pricing = match.get("pricing", {}) or {}
    try:
        prompt_cost = float(pricing.get("prompt", "0"))
        completion_cost = float(pricing.get("completion", "0"))
    except (TypeError, ValueError) as exc:
        raise ModelValidationError(
            f"Could not parse pricing for OpenRouter model '{model_id}': {pricing}"
        ) from exc

    if prompt_cost != 0.0 or completion_cost != 0.0:
        raise ModelValidationError(
            f"OpenRouter model '{model_id}' is NOT free (prompt=${prompt_cost}, "
            f"completion=${completion_cost} per token). This project requires an explicitly "
            "$0 model. Choose a free model (often suffixed ':free') and set OPENROUTER_MODEL "
            "accordingly."
        )

    logger.info(
        "openrouter_model_validated_free",
        extra={"event": "openrouter_model_validated_free", "model": model_id},
    )

