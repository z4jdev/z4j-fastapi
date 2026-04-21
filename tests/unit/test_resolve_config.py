"""Regression tests for ``z4j_fastapi.framework.resolve_config``.

The resolver merges explicit kwargs with ``Z4J_*`` environment
variables and Config defaults. Audit pass 8 (2026-04-21) surfaced
a truthy-fallback bug: ``brain_url or env.get("Z4J_BRAIN_URL")``
treated ``brain_url=""`` the same as ``brain_url=None`` and slid
quietly onto the env fallback. The fix uses ``is not None`` so an
explicit empty string fails fast against the required-field
validator, surfacing operator mistakes immediately instead of
silently picking up environment values the operator may not have
intended to honour.
"""

from __future__ import annotations

import pytest

from z4j_core.errors import ConfigError

from z4j_fastapi.framework import resolve_config


@pytest.fixture(autouse=True)
def _clear_z4j_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test starts with a clean environment.

    Strips every ``Z4J_*`` env var so the runner's or a previous
    test's leakage can never contaminate the assertions here.
    ``monkeypatch`` restores state at teardown.
    """
    import os

    for key in [k for k in os.environ if k.startswith("Z4J_")]:
        monkeypatch.delenv(key, raising=False)


class TestRequiredFieldsFailFast:
    """An explicit empty string must NOT silently fall back to the env var.

    Operators who pass empty kwargs have either made a mistake or
    are deliberately opting out; either way, the adapter should
    surface ``ConfigError`` rather than reach for an environment
    value the operator may not even be aware of.
    """

    def test_empty_brain_url_does_not_fall_back_to_env(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("Z4J_BRAIN_URL", "http://env-url:7700")
        monkeypatch.setenv("Z4J_TOKEN", "env-token")
        monkeypatch.setenv("Z4J_PROJECT_ID", "env-project")
        with pytest.raises(ConfigError, match="brain_url"):
            resolve_config(brain_url="", token="t", project_id="p")

    def test_empty_token_does_not_fall_back_to_env(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("Z4J_BRAIN_URL", "http://env-url:7700")
        monkeypatch.setenv("Z4J_TOKEN", "env-token")
        monkeypatch.setenv("Z4J_PROJECT_ID", "env-project")
        with pytest.raises(ConfigError, match="token"):
            resolve_config(
                brain_url="http://u", token="", project_id="p",
            )

    def test_empty_project_id_does_not_fall_back_to_env(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("Z4J_BRAIN_URL", "http://env-url:7700")
        monkeypatch.setenv("Z4J_TOKEN", "env-token")
        monkeypatch.setenv("Z4J_PROJECT_ID", "env-project")
        with pytest.raises(ConfigError, match="project_id"):
            resolve_config(
                brain_url="http://u", token="t", project_id="",
            )

    def test_all_three_empty_lists_all_missing(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # The original bug: resolve_config(brain_url='', token='',
        # project_id='') silently built a config from Z4J_* env
        # vars. The fix makes every one of the three explicit empty
        # strings appear in the error details so the operator sees
        # *which* field they forgot to fill in.
        monkeypatch.setenv("Z4J_BRAIN_URL", "http://env-url:7700")
        monkeypatch.setenv("Z4J_TOKEN", "env-token")
        monkeypatch.setenv("Z4J_PROJECT_ID", "env-project")
        with pytest.raises(ConfigError) as excinfo:
            resolve_config(brain_url="", token="", project_id="")
        details = excinfo.value.details or {}
        missing = details.get("missing", [])
        assert any("brain_url" in m for m in missing), missing
        assert any("token" in m for m in missing), missing
        assert any("project_id" in m for m in missing), missing


class TestNoneKwargFallsBackToEnv:
    """``None`` (kwarg not passed) still falls back to the env - that is
    the documented precedence rule and must continue to hold."""

    def test_none_brain_url_uses_env(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("Z4J_BRAIN_URL", "http://env-url:7700")
        monkeypatch.setenv("Z4J_TOKEN", "env-token")
        monkeypatch.setenv("Z4J_PROJECT_ID", "env-project")
        config = resolve_config()  # all kwargs default to None
        # Pydantic AnyHttpUrl normalises with a trailing slash; we
        # only care that the host:port chunk matches.
        assert "env-url:7700" in str(config.brain_url)
        assert config.token.get_secret_value() == "env-token"
        assert config.project_id == "env-project"

    def test_mixed_none_kwarg_and_explicit_kwarg(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # brain_url passed explicitly, other two via env.
        monkeypatch.setenv("Z4J_TOKEN", "env-token")
        monkeypatch.setenv("Z4J_PROJECT_ID", "env-project")
        config = resolve_config(brain_url="http://kwarg-url:7700")
        assert "kwarg-url:7700" in str(config.brain_url)
        assert config.token.get_secret_value() == "env-token"
        assert config.project_id == "env-project"


class TestKwargOverridesEnv:
    """Explicit non-empty kwargs always win over env vars."""

    def test_kwarg_brain_url_beats_env(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("Z4J_BRAIN_URL", "http://env-url:7700")
        config = resolve_config(
            brain_url="http://kwarg:7700",
            token="t",
            project_id="p",
        )
        assert "kwarg:7700" in str(config.brain_url)
        assert "env-url" not in str(config.brain_url)


class TestEmptyHmacSecret:
    """``hmac_secret`` is optional-but-recommended. Explicit empty
    string must not sneak the env var through either - the
    operator may be intentionally declaring "no HMAC on this
    agent" (``dev_mode`` handles the rest). Consistent with the
    required-field semantics above.
    """

    def test_empty_hmac_secret_does_not_use_env(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("Z4J_HMAC_SECRET", "env-secret-do-not-use")
        config = resolve_config(
            brain_url="http://u",
            token="t",
            project_id="p",
            hmac_secret="",
            dev_mode=True,  # dev mode allows absent hmac_secret
        )
        assert config.hmac_secret in (None, "")
