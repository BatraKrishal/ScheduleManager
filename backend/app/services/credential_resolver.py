from __future__ import annotations

import logging
import os
from typing import NamedTuple, Optional

logger = logging.getLogger("credential_resolver")


class CredentialResolution(NamedTuple):
    api_key: Optional[str]
    model: str
    source: str  # "EXPLICIT", "DEDICATED", "LEGACY_FALLBACK", "NONE"


class CredentialResolver:
    """
    Authoritative resolver for server-side LLM credentials and model configurations.
    Enforces independent credential isolation between Time Agent and ExtractionService,
    while managing governed, non-silent legacy fallback.

    GOVERNANCE RULES:
    1. Primary credentials: TIME_AGENT_GEMINI_API_KEY and EXTRACTION_GEMINI_API_KEY.
    2. Shared GEMINI_API_KEY is a temporary backward-compatibility mechanism ONLY,
       not the desired production configuration.
    3. Production environments (ENVIRONMENT=production) do NOT fall back to GEMINI_API_KEY
       unless explicitly enabled via ALLOW_LEGACY_GEMINI_FALLBACK=true.
    4. Credential values are NEVER printed or logged under any circumstances.
    """

    @classmethod
    def is_production(cls) -> bool:
        """
        Detects if the application is executing within a production environment.
        Checks standard environment variables: ENVIRONMENT, APP_ENV, ENV.
        """
        env = (
            os.getenv("ENVIRONMENT")
            or os.getenv("APP_ENV")
            or os.getenv("ENV")
            or ""
        )
        return env.strip().lower() in ("production", "prod")

    @classmethod
    def is_legacy_fallback_allowed(cls) -> bool:
        """
        Determines whether legacy fallback to shared GEMINI_API_KEY is permitted.

        - If ALLOW_LEGACY_GEMINI_FALLBACK is explicitly configured, its boolean value governs.
        - In production (ENVIRONMENT=production), fallback is strictly DISABLED by default
          and requires explicit ALLOW_LEGACY_GEMINI_FALLBACK=true.
        - In non-production environments (dev/test), fallback is allowed by default for
          local convenience, but always emits a non-silent security warning.
        """
        val = os.getenv("ALLOW_LEGACY_GEMINI_FALLBACK")
        if val is not None:
            return val.strip().lower() in ("true", "1", "yes")

        # In production environments, never fall back silently
        if cls.is_production():
            return False

        # Non-production default: allow backward compatibility
        return True

    @classmethod
    def resolve_time_agent_credentials(
        cls,
        explicit_key: Optional[str] = None,
        explicit_model: Optional[str] = None,
    ) -> CredentialResolution:
        """
        Resolves the Gemini API key and model for the Time Agent.
        Precedence:
        1. Explicitly supplied key (e.g. for testing)
        2. TIME_AGENT_GEMINI_API_KEY (primary production configuration)
        3. GEMINI_API_KEY (temporary legacy fallback if explicitly permitted or allowed)
        """
        model = (
            explicit_model
            or os.getenv("TIME_AGENT_LLM_MODEL")
            or os.getenv("LLM_MODEL")
            or "gemini-2.5-flash"
        )
        if explicit_key:
            return CredentialResolution(api_key=explicit_key, model=model, source="EXPLICIT")

        dedicated_key = os.getenv("TIME_AGENT_GEMINI_API_KEY")
        if dedicated_key:
            return CredentialResolution(api_key=dedicated_key, model=model, source="DEDICATED")

        legacy_key = os.getenv("GEMINI_API_KEY")
        if legacy_key:
            if cls.is_legacy_fallback_allowed():
                logger.warning(
                    "[SECURITY NOTICE] Time Agent is using legacy shared GEMINI_API_KEY. "
                    "This is a temporary backward-compatibility fallback and NOT the desired production configuration. "
                    "Configure TIME_AGENT_GEMINI_API_KEY for dedicated credential isolation."
                )
                return CredentialResolution(api_key=legacy_key, model=model, source="LEGACY_FALLBACK")
            else:
                logger.error(
                    "[CREDENTIAL ERROR] TIME_AGENT_GEMINI_API_KEY is not configured and legacy "
                    "fallback to GEMINI_API_KEY is disabled or disallowed in this environment. "
                    "Set TIME_AGENT_GEMINI_API_KEY or configure ALLOW_LEGACY_GEMINI_FALLBACK=true."
                )
                return CredentialResolution(api_key=None, model=model, source="NONE")

        return CredentialResolution(api_key=None, model=model, source="NONE")

    @classmethod
    def resolve_extraction_credentials(
        cls,
        explicit_key: Optional[str] = None,
        explicit_model: Optional[str] = None,
    ) -> CredentialResolution:
        """
        Resolves the Gemini API key and model for document artifact extraction.
        Precedence:
        1. Explicitly supplied key (e.g. for testing)
        2. EXTRACTION_GEMINI_API_KEY (primary production configuration)
        3. GEMINI_API_KEY (temporary legacy fallback if explicitly permitted or allowed)
        """
        model = (
            explicit_model
            or os.getenv("EXTRACTION_LLM_MODEL")
            or os.getenv("LLM_MODEL")
            or "gemini-3.5-flash"
        )
        if explicit_key:
            return CredentialResolution(api_key=explicit_key, model=model, source="EXPLICIT")

        dedicated_key = os.getenv("EXTRACTION_GEMINI_API_KEY")
        if dedicated_key:
            return CredentialResolution(api_key=dedicated_key, model=model, source="DEDICATED")

        legacy_key = os.getenv("GEMINI_API_KEY")
        if legacy_key:
            if cls.is_legacy_fallback_allowed():
                logger.warning(
                    "[SECURITY NOTICE] ExtractionService is using legacy shared GEMINI_API_KEY. "
                    "This is a temporary backward-compatibility fallback and NOT the desired production configuration. "
                    "Configure EXTRACTION_GEMINI_API_KEY for dedicated credential isolation."
                )
                return CredentialResolution(api_key=legacy_key, model=model, source="LEGACY_FALLBACK")
            else:
                logger.error(
                    "[CREDENTIAL ERROR] EXTRACTION_GEMINI_API_KEY is not configured and legacy "
                    "fallback to GEMINI_API_KEY is disabled or disallowed in this environment. "
                    "Set EXTRACTION_GEMINI_API_KEY or configure ALLOW_LEGACY_GEMINI_FALLBACK=true."
                )
                return CredentialResolution(api_key=None, model=model, source="NONE")

        return CredentialResolution(api_key=None, model=model, source="NONE")
