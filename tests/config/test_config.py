"""Tests for environment-variable resolution in FantasyConfig.

FantasyConfig reads os.getenv at class-definition time and the module calls
load_dotenv() on import, so each case reloads the module under a controlled
environment. load_dotenv is neutralized so a developer's local .env can't make
these deterministic assertions flaky.
"""

import importlib

import pytest

import fantasy_manager.config.config as config_module


@pytest.fixture
def reload_config(monkeypatch):
    """Reload FantasyConfig with the given env, ignoring any local .env file."""
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)

    def _reload(env):
        for key, value in env.items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, value)
        return importlib.reload(config_module).FantasyConfig

    yield _reload
    # Restore the module for any later test that imports the real config.
    monkeypatch.delenv("YAHOO_COOKIE", raising=False)
    monkeypatch.delenv("YAHOO_CRUMB", raising=False)
    importlib.reload(config_module)


def test_yahoo_cookie_and_crumb_resolve_from_env(reload_config):
    config = reload_config({"YAHOO_COOKIE": "cookie-abc", "YAHOO_CRUMB": "crumb-xyz"})

    assert config.YAHOO_COOKIE == "cookie-abc"
    assert config.YAHOO_CRUMB == "crumb-xyz"


def test_yahoo_cookie_and_crumb_default_to_none(reload_config):
    config = reload_config({"YAHOO_COOKIE": None, "YAHOO_CRUMB": None})

    assert config.YAHOO_COOKIE is None
    assert config.YAHOO_CRUMB is None


def test_timing_knobs_default_to_current_values(reload_config):
    config = reload_config(
        {"PRE_FLIGHT_CHECK_SECS": None, "FIRE_EARLY_BUFFER_SECS": None}
    )

    assert config.PRE_FLIGHT_CHECK_SECS == 30
    assert config.FIRE_EARLY_BUFFER_SECS == 0.2


def test_timing_knobs_resolve_and_cast_from_env(reload_config):
    config = reload_config(
        {"PRE_FLIGHT_CHECK_SECS": "45", "FIRE_EARLY_BUFFER_SECS": "0.5"}
    )

    assert config.PRE_FLIGHT_CHECK_SECS == 45
    assert config.FIRE_EARLY_BUFFER_SECS == 0.5


NEWS_ENV_VARS = (
    "BLUESKY_HANDLE",
    "BLUESKY_APP_PASSWORD",
    "BLUESKY_LIST_URI",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "NEWS_ALERT_EMAIL",
)


def test_news_env_vars_resolve_from_env(reload_config):
    config = reload_config({name: f"value-{name}" for name in NEWS_ENV_VARS})

    for name in NEWS_ENV_VARS:
        assert getattr(config, name) == f"value-{name}"


def test_news_env_vars_default_to_none(reload_config):
    config = reload_config({name: None for name in NEWS_ENV_VARS})

    for name in NEWS_ENV_VARS:
        assert getattr(config, name) is None
