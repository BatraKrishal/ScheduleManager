import logging
from unittest.mock import patch
import pytest

from app.services.credential_resolver import CredentialResolution, CredentialResolver


def test_both_dedicated_keys_present(monkeypatch):
    """
    When both dedicated keys are configured:
    - Time Agent resolves to TIME_AGENT_GEMINI_API_KEY (DEDICATED)
    - Extraction resolves to EXTRACTION_GEMINI_API_KEY (DEDICATED)
    - Legacy GEMINI_API_KEY is ignored even if set
    """
    monkeypatch.setenv("TIME_AGENT_GEMINI_API_KEY", "secret-time-dedicated-key")
    monkeypatch.setenv("EXTRACTION_GEMINI_API_KEY", "secret-extract-dedicated-key")
    monkeypatch.setenv("GEMINI_API_KEY", "secret-legacy-shared-key")

    time_res = CredentialResolver.resolve_time_agent_credentials()
    extract_res = CredentialResolver.resolve_extraction_credentials()

    assert time_res.api_key == "secret-time-dedicated-key"
    assert time_res.source == "DEDICATED"

    assert extract_res.api_key == "secret-extract-dedicated-key"
    assert extract_res.source == "DEDICATED"


def test_one_dedicated_key_missing(monkeypatch):
    """
    When only one dedicated key is present:
    - The configured service resolves to its DEDICATED key.
    - The missing service falls back to LEGACY_FALLBACK (if allowed) or NONE (if disabled).
    """
    # Time Agent configured, Extraction unconfigured
    monkeypatch.setenv("TIME_AGENT_GEMINI_API_KEY", "secret-time-dedicated-key")
    monkeypatch.delenv("EXTRACTION_GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "secret-legacy-shared-key")
    monkeypatch.setenv("ALLOW_LEGACY_GEMINI_FALLBACK", "true")

    time_res = CredentialResolver.resolve_time_agent_credentials()
    extract_res = CredentialResolver.resolve_extraction_credentials()

    assert time_res.api_key == "secret-time-dedicated-key"
    assert time_res.source == "DEDICATED"
    assert extract_res.api_key == "secret-legacy-shared-key"
    assert extract_res.source == "LEGACY_FALLBACK"

    # Now disable legacy fallback
    monkeypatch.setenv("ALLOW_LEGACY_GEMINI_FALLBACK", "false")
    extract_res_disabled = CredentialResolver.resolve_extraction_credentials()
    time_res_still_ok = CredentialResolver.resolve_time_agent_credentials()

    assert time_res_still_ok.api_key == "secret-time-dedicated-key"
    assert time_res_still_ok.source == "DEDICATED"
    assert extract_res_disabled.api_key is None
    assert extract_res_disabled.source == "NONE"


def test_only_legacy_key_present(monkeypatch):
    """
    When dedicated keys are absent and only legacy GEMINI_API_KEY is present:
    - If fallback allowed: resolves with source LEGACY_FALLBACK
    - If fallback disabled: resolves with source NONE and api_key None
    """
    monkeypatch.delenv("TIME_AGENT_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("EXTRACTION_GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "secret-legacy-shared-key")
    monkeypatch.setenv("ALLOW_LEGACY_GEMINI_FALLBACK", "true")

    time_res = CredentialResolver.resolve_time_agent_credentials()
    extract_res = CredentialResolver.resolve_extraction_credentials()

    assert time_res.api_key == "secret-legacy-shared-key"
    assert time_res.source == "LEGACY_FALLBACK"
    assert extract_res.api_key == "secret-legacy-shared-key"
    assert extract_res.source == "LEGACY_FALLBACK"

    # With fallback disabled explicitly
    monkeypatch.setenv("ALLOW_LEGACY_GEMINI_FALLBACK", "false")
    time_res_no_fallback = CredentialResolver.resolve_time_agent_credentials()
    extract_res_no_fallback = CredentialResolver.resolve_extraction_credentials()

    assert time_res_no_fallback.api_key is None
    assert time_res_no_fallback.source == "NONE"
    assert extract_res_no_fallback.api_key is None
    assert extract_res_no_fallback.source == "NONE"


def test_production_environment_blocks_silent_fallback(monkeypatch):
    """
    Requirement 4: In production (ENVIRONMENT=production), do not silently fall back
    to GEMINI_API_KEY unless explicitly enabled/configured via ALLOW_LEGACY_GEMINI_FALLBACK=true.
    """
    monkeypatch.delenv("TIME_AGENT_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("EXTRACTION_GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "secret-legacy-shared-key")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("ALLOW_LEGACY_GEMINI_FALLBACK", raising=False)

    # In production without explicit opt-in, legacy fallback is strictly blocked
    assert CredentialResolver.is_production() is True
    assert CredentialResolver.is_legacy_fallback_allowed() is False

    time_res = CredentialResolver.resolve_time_agent_credentials()
    extract_res = CredentialResolver.resolve_extraction_credentials()

    assert time_res.api_key is None
    assert time_res.source == "NONE"
    assert extract_res.api_key is None
    assert extract_res.source == "NONE"

    # When explicitly opted-in in production
    monkeypatch.setenv("ALLOW_LEGACY_GEMINI_FALLBACK", "true")
    assert CredentialResolver.is_legacy_fallback_allowed() is True

    time_res_opted = CredentialResolver.resolve_time_agent_credentials()
    extract_res_opted = CredentialResolver.resolve_extraction_credentials()

    assert time_res_opted.api_key == "secret-legacy-shared-key"
    assert time_res_opted.source == "LEGACY_FALLBACK"
    assert extract_res_opted.api_key == "secret-legacy-shared-key"
    assert extract_res_opted.source == "LEGACY_FALLBACK"


def test_no_keys_present(monkeypatch):
    """
    When no API keys are present anywhere in the environment:
    - Both resolve to None with source NONE
    """
    monkeypatch.delenv("TIME_AGENT_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("EXTRACTION_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    time_res = CredentialResolver.resolve_time_agent_credentials()
    extract_res = CredentialResolver.resolve_extraction_credentials()

    assert time_res.api_key is None
    assert time_res.source == "NONE"
    assert extract_res.api_key is None
    assert extract_res.source == "NONE"


def test_independent_model_id_configuration(monkeypatch):
    """
    Requirement 5: Verify the two model IDs are configurable independently.
    """
    # 1. Dedicated independent models
    monkeypatch.setenv("TIME_AGENT_LLM_MODEL", "gemini-2.5-flash-agent")
    monkeypatch.setenv("EXTRACTION_LLM_MODEL", "gemini-3.5-flash-extract")

    time_res = CredentialResolver.resolve_time_agent_credentials()
    extract_res = CredentialResolver.resolve_extraction_credentials()

    assert time_res.model == "gemini-2.5-flash-agent"
    assert extract_res.model == "gemini-3.5-flash-extract"

    # 2. Defaults when variables are unset
    monkeypatch.delenv("TIME_AGENT_LLM_MODEL", raising=False)
    monkeypatch.delenv("EXTRACTION_LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    time_res_default = CredentialResolver.resolve_time_agent_credentials()
    extract_res_default = CredentialResolver.resolve_extraction_credentials()

    assert time_res_default.model == "gemini-2.5-flash"
    assert extract_res_default.model == "gemini-3.5-flash"

    # 3. Fallback to shared LLM_MODEL if dedicated are not set
    monkeypatch.setenv("LLM_MODEL", "gemini-custom-shared")

    time_res_shared = CredentialResolver.resolve_time_agent_credentials()
    extract_res_shared = CredentialResolver.resolve_extraction_credentials()

    assert time_res_shared.model == "gemini-custom-shared"
    assert extract_res_shared.model == "gemini-custom-shared"


def test_explicit_key_and_model_overrides():
    """
    Explicit arguments override environment variables and yield source EXPLICIT.
    """
    res = CredentialResolver.resolve_time_agent_credentials(
        explicit_key="manual-override-key",
        explicit_model="custom-override-model",
    )
    assert res.api_key == "manual-override-key"
    assert res.model == "custom-override-model"
    assert res.source == "EXPLICIT"

    res_ext = CredentialResolver.resolve_extraction_credentials(
        explicit_key="manual-ext-key",
        explicit_model="custom-ext-model",
    )
    assert res_ext.api_key == "manual-ext-key"
    assert res_ext.model == "custom-ext-model"
    assert res_ext.source == "EXPLICIT"


def test_credential_values_never_logged_or_printed(monkeypatch, caplog):
    """
    Requirement 8: Do not print or log credential values.
    Verify that secret credential values never appear in log messages or records.
    """
    secret_time_key = "sk-super-secret-time-key-99999"
    secret_extract_key = "sk-super-secret-extract-key-88888"
    secret_legacy_key = "sk-super-secret-legacy-key-77777"

    monkeypatch.delenv("TIME_AGENT_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("EXTRACTION_GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", secret_legacy_key)
    monkeypatch.setenv("ALLOW_LEGACY_GEMINI_FALLBACK", "true")

    with caplog.at_level(logging.DEBUG):
        # Trigger fallback warnings
        CredentialResolver.resolve_time_agent_credentials()
        CredentialResolver.resolve_extraction_credentials()

        # Trigger error logs
        monkeypatch.setenv("ALLOW_LEGACY_GEMINI_FALLBACK", "false")
        CredentialResolver.resolve_time_agent_credentials()
        CredentialResolver.resolve_extraction_credentials()

    # Verify captured log text
    all_logs = caplog.text
    assert secret_time_key not in all_logs
    assert secret_extract_key not in all_logs
    assert secret_legacy_key not in all_logs

    for record in caplog.records:
        assert secret_time_key not in record.message
        assert secret_extract_key not in record.message
        assert secret_legacy_key not in record.message


def test_zero_real_gemini_api_calls_in_tests(monkeypatch):
    """
    Requirement 7: Do not make real Gemini API calls in the test suite.
    Verify that resolving credentials performs strictly offline environment inspection.
    """
    with patch("httpx.Client.post") as mock_post:
        monkeypatch.setenv("TIME_AGENT_GEMINI_API_KEY", "mock-key")
        monkeypatch.setenv("EXTRACTION_GEMINI_API_KEY", "mock-key")

        CredentialResolver.resolve_time_agent_credentials()
        CredentialResolver.resolve_extraction_credentials()

        assert mock_post.call_count == 0
