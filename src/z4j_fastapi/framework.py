"""The :class:`FastAPIFrameworkAdapter`.

Implements :class:`z4j_core.protocols.FrameworkAdapter` for FastAPI.
The adapter is constructed inside :func:`extension.install_z4j` or
:func:`extension.z4j_lifespan`, which resolve configuration from
explicit kwargs and environment variables, then hand the resulting
Config to the adapter and the agent runtime.

FastAPI has no app-level settings dict like Django's ``settings.Z4J``.
Configuration comes from either:

1. Explicit kwargs passed to ``install_z4j`` / ``z4j_lifespan``
2. ``Z4J_*`` environment variables (same names as the Django adapter)
3. Defaults declared on :class:`z4j_core.models.Config`
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from z4j_core.errors import ConfigError
from z4j_core.models import Config, DiscoveryHints, RequestContext, User

logger = logging.getLogger("z4j.agent.fastapi.framework")


class FastAPIFrameworkAdapter:
    """Framework adapter for FastAPI.

    Implements the :class:`FrameworkAdapter` Protocol via duck typing
    (no inheritance - see ``docs/patterns.md``). Lifecycle hooks are
    stored as plain lists; :meth:`fire_startup` and :meth:`fire_shutdown`
    invoke them when called by the extension module.

    Attributes:
        name: Always ``"fastapi"``.
        _config: The resolved :class:`Config` for this process.
    """

    name: str = "fastapi"

    #: Worker-first protocol (1.2.0+) role hint. FastAPI agents run
    #: under uvicorn / hypercorn / gunicorn-worker; default "web".
    default_worker_role: str = "web"

    def __init__(self, config: Config) -> None:
        self._config = config
        self._startup_hooks: list[Callable[[], None]] = []
        self._shutdown_hooks: list[Callable[[], None]] = []

    # ------------------------------------------------------------------
    # FrameworkAdapter Protocol
    # ------------------------------------------------------------------

    def discover_config(self) -> Config:
        return self._config

    def discovery_hints(self) -> DiscoveryHints:
        return DiscoveryHints(framework_name="fastapi")

    def current_context(self) -> RequestContext | None:
        # FastAPI does not have a global "current request" by default.
        # A future middleware could stash the Starlette request on a
        # ContextVar (like the Django adapter does). For now, return
        # None - the agent handles this gracefully.
        return None

    def current_user(self) -> User | None:
        # Same rationale as current_context - no global user context
        # in FastAPI without explicit middleware.
        return None

    def on_startup(self, hook: Callable[[], None]) -> None:
        self._startup_hooks.append(hook)

    def on_shutdown(self, hook: Callable[[], None]) -> None:
        self._shutdown_hooks.append(hook)

    def register_admin_view(self, view: Any) -> None:  # noqa: ARG002
        # No-op. FastAPI does not have a built-in admin panel.
        return None

    # ------------------------------------------------------------------
    # Internal helpers used by the extension module
    # ------------------------------------------------------------------

    def fire_startup(self) -> None:
        """Invoke every registered startup hook in order.

        Called once after the agent runtime has connected. Exceptions
        from individual hooks are caught and logged so a single bad
        hook does not abort the others.
        """
        for hook in self._startup_hooks:
            try:
                hook()
            except Exception:  # noqa: BLE001
                logger.exception("z4j fastapi startup hook failed")

    def fire_shutdown(self) -> None:
        """Invoke every registered shutdown hook in order.

        Called once during application shutdown. Same exception
        semantics as :meth:`fire_startup`.
        """
        for hook in self._shutdown_hooks:
            try:
                hook()
            except Exception:  # noqa: BLE001
                logger.exception("z4j fastapi shutdown hook failed")


# ---------------------------------------------------------------------------
# Configuration resolution
# ---------------------------------------------------------------------------


def resolve_config(
    *,
    brain_url: str | None = None,
    token: str | None = None,
    project_id: str | None = None,
    hmac_secret: str | None = None,
    environment: str | None = None,
    transport: str | None = None,
    agent_id: str | None = None,
    log_level: str | None = None,
    engines: list[str] | None = None,
    schedulers: list[str] | None = None,
    tags: dict[str, str] | None = None,
    dev_mode: bool | None = None,
    strict_mode: bool | None = None,
    autostart: bool | None = None,
    heartbeat_seconds: int | None = None,
    buffer_path: str | Path | None = None,
    buffer_max_events: int | None = None,
    buffer_max_bytes: int | None = None,
    max_payload_bytes: int | None = None,
) -> Config:
    """Build a :class:`Config` from explicit kwargs and environment variables.

    Resolution priority (highest first):

    1. Explicit keyword arguments (passed to ``install_z4j`` / ``z4j_lifespan``)
    2. ``Z4J_*`` environment variables
    3. Defaults declared on :class:`z4j_core.models.Config`

    Raises:
        ConfigError: Required values are missing or invalid.
    """
    from pydantic import ValidationError

    env = os.environ
    resolved: dict[str, Any] = {}

    # Required fields - explicit kwarg takes priority over env var.
    # Use ``is not None`` so an operator who passes an explicit
    # empty string fails the non-empty required-field check below
    # instead of silently sliding onto the env fallback. A falsy
    # ``or`` would have treated ``brain_url=""`` the same as
    # ``brain_url=None`` (not passed) - surfaced by audit pass 8
    # 2026-04-21.
    r_brain_url = brain_url if brain_url is not None else env.get("Z4J_BRAIN_URL")
    r_token = token if token is not None else env.get("Z4J_TOKEN")
    r_project_id = project_id if project_id is not None else env.get("Z4J_PROJECT_ID")

    missing: list[str] = []
    if not r_brain_url:
        missing.append("brain_url (or Z4J_BRAIN_URL)")
    if not r_token:
        missing.append("token (or Z4J_TOKEN)")
    if not r_project_id:
        missing.append("project_id (or Z4J_PROJECT_ID)")
    if missing:
        raise ConfigError(
            "missing required Z4J settings: " + ", ".join(missing),
            details={"missing": missing},
        )

    resolved["brain_url"] = r_brain_url
    resolved["token"] = r_token
    resolved["project_id"] = r_project_id

    # HMAC secret - same ``is not None`` discipline as the
    # required fields. Explicit ``hmac_secret=""`` means the
    # caller is deliberately opting out; we do not quietly
    # rescue with an env fallback.
    r_hmac_secret = (
        hmac_secret if hmac_secret is not None else env.get("Z4J_HMAC_SECRET")
    )
    if r_hmac_secret:
        resolved["hmac_secret"] = r_hmac_secret

    # Optional string fields - kwarg > env > omit (use Config default)
    _maybe_set_str(resolved, "environment", environment, env, "Z4J_ENVIRONMENT")
    _maybe_set_str(resolved, "transport", transport, env, "Z4J_TRANSPORT")
    # Long-poll agent UUID - required by Config when transport='longpoll'.
    # Audit 2026-04-24 Medium-2: resolver was missing this field, so
    # operators switching to long-poll hit silent HMAC mismatches.
    _maybe_set_str(resolved, "agent_id", agent_id, env, "Z4J_AGENT_ID")
    _maybe_set_str(resolved, "log_level", log_level, env, "Z4J_LOG_LEVEL")

    # List fields
    if engines is not None:
        resolved["engines"] = engines
    elif "Z4J_ENGINES" in env:
        resolved["engines"] = [
            x.strip() for x in env["Z4J_ENGINES"].split(",") if x.strip()
        ]

    if schedulers is not None:
        resolved["schedulers"] = schedulers
    elif "Z4J_SCHEDULERS" in env:
        resolved["schedulers"] = [
            x.strip() for x in env["Z4J_SCHEDULERS"].split(",") if x.strip()
        ]

    # Tags
    if tags is not None:
        resolved["tags"] = tags

    # Booleans
    _maybe_set_bool(resolved, "dev_mode", dev_mode, env, "Z4J_DEV_MODE")
    _maybe_set_bool(resolved, "strict_mode", strict_mode, env, "Z4J_STRICT_MODE")
    _maybe_set_bool(resolved, "autostart", autostart, env, "Z4J_AUTOSTART")

    # Integers
    _maybe_set_int(resolved, "heartbeat_seconds", heartbeat_seconds, env, "Z4J_HEARTBEAT_SECONDS")
    _maybe_set_int(resolved, "buffer_max_events", buffer_max_events, env, "Z4J_BUFFER_MAX_EVENTS")
    _maybe_set_int(resolved, "buffer_max_bytes", buffer_max_bytes, env, "Z4J_BUFFER_MAX_BYTES")
    _maybe_set_int(resolved, "max_payload_bytes", max_payload_bytes, env, "Z4J_MAX_PAYLOAD_BYTES")

    # Path - clamped to the agent's allowed buffer roots
    # (``~/.z4j`` / ``$TMPDIR/z4j-{uid}``). Audit 2026-04-24 Low-2.
    from z4j_bare.storage import clamp_buffer_path

    raw_buffer_path: Path | None = None
    if buffer_path is not None:
        raw_buffer_path = Path(buffer_path)
    elif "Z4J_BUFFER_PATH" in env:
        raw_buffer_path = Path(env["Z4J_BUFFER_PATH"])
    if raw_buffer_path is not None:
        try:
            resolved["buffer_path"] = clamp_buffer_path(raw_buffer_path)
        except ValueError as exc:
            raise ConfigError(str(exc)) from None

    try:
        return Config(**resolved)
    except ValidationError as exc:
        # Redact values from the error message (same pattern as Django adapter).
        details = [
            {
                "loc": ".".join(str(p) for p in err["loc"]),
                "type": err["type"],
            }
            for err in exc.errors()
        ]
        raise ConfigError(
            f"invalid Z4J configuration ({len(details)} field(s))",
            details={"errors": details},
        ) from None
    except (TypeError, ValueError) as exc:
        raise ConfigError(
            f"invalid Z4J configuration: {type(exc).__name__}",
        ) from None


# ---------------------------------------------------------------------------
# Engine / scheduler discovery
# ---------------------------------------------------------------------------


def discover_engines(
    celery_app: Any = None,
    *,
    rq_app: Any = None,
    arq_redis_settings: Any = None,
    arq_function_names: Any = (),
    arq_queue_name: str = "arq:queue",
    dramatiq_broker: Any = None,
    huey: Any = None,
    taskiq_broker: Any = None,
) -> list[Any]:
    """Try to import every supported engine adapter and instantiate it.

    v1.1.0 supports auto-discovery of all 6 engines: celery, rq, arq,
    dramatiq, huey, taskiq. FastAPI has no Django-style global app
    convention so the operator passes the engine handle as a kwarg
    via ``z4j_lifespan(...)`` / ``install_z4j(...)``. Multiple engines
    can co-exist in one FastAPI process.

    Each kwarg is the engine's native object:

    - ``celery_app`` — Celery instance
    - ``rq_app`` — RQ wrapper (or operator's duck-typed object); see
      :class:`RqEngineAdapter` docstring for the shape
    - ``arq_redis_settings`` — arq RedisSettings or pool
    - ``arq_function_names`` — iterable of registered arq function names
    - ``dramatiq_broker`` — Dramatiq broker (or None to fall back to
      ``dramatiq.get_broker()`` IFF actors are registered on it)
    - ``huey`` — Huey instance
    - ``taskiq_broker`` — taskiq broker

    Adapters not installed (their package not pip-installed) are
    skipped silently. Adapters whose handle wasn't passed are skipped
    silently.
    """
    engines: list[Any] = []

    for adapter in (
        _try_import_celery_engine(celery_app),
        _try_import_rq_engine(rq_app),
        _try_import_arq_engine(
            arq_redis_settings, arq_function_names, arq_queue_name,
        ),
        _try_import_dramatiq_engine(dramatiq_broker),
        _try_import_huey_engine(huey),
        _try_import_taskiq_engine(taskiq_broker),
    ):
        if adapter is not None:
            engines.append(adapter)

    if not engines:
        logger.info(
            "z4j: no queue engine adapters discovered; the agent will run "
            "but will not capture task events. Install z4j-celery (or "
            "z4j-rq / z4j-arq / z4j-dramatiq / z4j-huey / z4j-taskiq) and "
            "pass the engine handle (celery_app=, rq_app=, etc.) to fix.",
        )
    return engines


def discover_schedulers(celery_app: Any = None) -> list[Any]:
    """Try to import every supported scheduler adapter."""
    schedulers: list[Any] = []

    beat = _try_import_celerybeat_scheduler(celery_app)
    if beat is not None:
        schedulers.append(beat)

    return schedulers


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _try_import_celery_engine(celery_app: Any) -> Any:
    """Best-effort import of CeleryEngineAdapter.

    Unlike the Django adapter, FastAPI does not have a convention for
    where the Celery app lives. The user must pass it explicitly.
    """
    if celery_app is None:
        return None

    try:
        from z4j_celery.engine import CeleryEngineAdapter
    except ImportError:
        logger.warning(
            "z4j: celery_app was provided but z4j-celery is not installed; "
            "pip install z4j-celery to enable Celery integration.",
        )
        return None

    return CeleryEngineAdapter(celery_app=celery_app)


def _try_import_celerybeat_scheduler(celery_app: Any) -> Any:
    """Best-effort import of CeleryBeatSchedulerAdapter."""
    try:
        from z4j_celerybeat.scheduler import CeleryBeatSchedulerAdapter
    except ImportError:
        return None

    return CeleryBeatSchedulerAdapter(celery_app=celery_app)


def _try_import_rq_engine(rq_app: Any) -> Any:
    """Best-effort import of :class:`RqEngineAdapter`.

    Returns None if z4j-rq isn't installed or no rq_app was passed.
    """
    if rq_app is None:
        return None
    try:
        from z4j_rq.engine import RqEngineAdapter
    except ImportError:
        logger.warning(
            "z4j: rq_app was provided but z4j-rq is not installed; "
            "pip install z4j-rq to enable RQ integration.",
        )
        return None
    return RqEngineAdapter(rq_app=rq_app)


def _try_import_arq_engine(
    redis_settings: Any,
    function_names: Any,
    queue_name: str,
) -> Any:
    """Best-effort import of :class:`ArqEngineAdapter`."""
    if redis_settings is None:
        return None
    try:
        from z4j_arq import ArqEngineAdapter
    except ImportError:
        logger.warning(
            "z4j: arq_redis_settings was provided but z4j-arq is not installed; "
            "pip install z4j-arq to enable arq integration.",
        )
        return None
    return ArqEngineAdapter(
        redis_settings=redis_settings,
        function_names=function_names,
        queue_name=queue_name,
    )


def _try_import_dramatiq_engine(broker: Any) -> Any:
    """Best-effort import of :class:`DramatiqEngineAdapter`.

    If ``broker`` is None, falls back to ``dramatiq.get_broker()``
    IFF at least one actor has been registered on it. Without the
    actor check we'd pick up dramatiq's auto-created default
    StubBroker in projects that never opted into Dramatiq.
    """
    try:
        from z4j_dramatiq.engine import DramatiqEngineAdapter
    except ImportError:
        return None

    if broker is None:
        try:
            import dramatiq
            candidate = dramatiq.get_broker()
            actors = getattr(candidate, "actors", None) or {}
            if actors:
                broker = candidate
        except Exception:  # noqa: BLE001
            return None
    if broker is None:
        return None
    return DramatiqEngineAdapter(broker=broker)


def _try_import_huey_engine(huey: Any) -> Any:
    """Best-effort import of :class:`HueyEngineAdapter`."""
    if huey is None:
        return None
    try:
        from z4j_huey import HueyEngineAdapter
    except ImportError:
        logger.warning(
            "z4j: huey was provided but z4j-huey is not installed; "
            "pip install z4j-huey to enable Huey integration.",
        )
        return None
    return HueyEngineAdapter(huey=huey)


def _try_import_taskiq_engine(broker: Any) -> Any:
    """Best-effort import of :class:`TaskiqEngineAdapter`."""
    if broker is None:
        return None
    try:
        from z4j_taskiq import TaskiqEngineAdapter
    except ImportError:
        logger.warning(
            "z4j: taskiq_broker was provided but z4j-taskiq is not installed; "
            "pip install z4j-taskiq to enable taskiq integration.",
        )
        return None
    return TaskiqEngineAdapter(broker=broker)


def _maybe_set_str(
    resolved: dict[str, Any],
    key: str,
    kwarg_value: str | None,
    env: os._Environ[str] | dict[str, str],
    env_key: str,
) -> None:
    if kwarg_value is not None:
        resolved[key] = kwarg_value
    elif env_key in env:
        resolved[key] = env[env_key]


def _maybe_set_bool(
    resolved: dict[str, Any],
    key: str,
    kwarg_value: bool | None,
    env: os._Environ[str] | dict[str, str],
    env_key: str,
) -> None:
    if kwarg_value is not None:
        resolved[key] = kwarg_value
    elif env_key in env:
        resolved[key] = env[env_key].strip().lower() in ("1", "true", "yes", "on")


def _maybe_set_int(
    resolved: dict[str, Any],
    key: str,
    kwarg_value: int | None,
    env: os._Environ[str] | dict[str, str],
    env_key: str,
) -> None:
    if kwarg_value is not None:
        resolved[key] = kwarg_value
    elif env_key in env:
        try:
            resolved[key] = int(env[env_key])
        except ValueError as exc:
            raise ConfigError(f"{env_key} must be an integer: {exc}") from exc


__all__ = [
    "FastAPIFrameworkAdapter",
    "discover_engines",
    "discover_schedulers",
    "resolve_config",
]
