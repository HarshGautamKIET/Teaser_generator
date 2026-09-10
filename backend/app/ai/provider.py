"""Provider selection."""

import logging
from functools import lru_cache

from app.ai.base import AIProvider
from app.ai.fake import FakeProvider
from app.ai.gemini import GeminiProvider
from app.ai.keyring import build_keyring
from app.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_ai_provider() -> AIProvider:
    """Return the configured provider (FastAPI dependency).

    Cached deliberately: the provider owns the key ring, and a fresh one per
    call would reset the pool to the first key on every job -- so an exhausted
    key would be retried forever instead of retired.
    """
    settings = get_settings()
    if settings.ai_provider == "fake":
        logger.warning("Using the FAKE AI provider -- results are not real analysis.")
        return FakeProvider()

    keyring = build_keyring(settings.gemini_api_key, settings.gemini_api_keys)
    logger.info("Gemini configured with %d API key(s)", len(keyring))
    return GeminiProvider(
        keyring=keyring,
        model=settings.gemini_model,
        request_timeout_seconds=settings.gemini_request_timeout_seconds,
        generate_timeout_seconds=settings.gemini_generate_timeout_seconds,
    )
