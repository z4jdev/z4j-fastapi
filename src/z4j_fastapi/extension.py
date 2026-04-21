"""FastAPI integration entry points.

Provides two usage patterns for wiring z4j into a FastAPI application:

**Pattern 1 - lifespan (recommended)**::

    from fastapi import FastAPI
    from z4j_fastapi import z4j_lifespan

    app = FastAPI(lifespan=z4j_lifespan(
        brain_url="http://localhost:7700",
        token="your-token",
        celery_app=celery_app,
    ))

**Pattern 2 - manual install**::

    from fastapi import FastAPI
    from z4j_fastapi import install_z4j

    app = FastAPI()
    install_z4j(app, brain_url="http://localhost:7700", token="your-token")

Both patterns wrap all z4j work in try/except so that a failure inside
z4j never crashes the FastAPI application. The host app is more
important than our observability tool.
"""

from __future__ import annotations

import atexit
import logging
import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from z4j_bare.runtime import AgentRuntime

from z4j_fastapi.framework import (
    FastAPIFrameworkAdapter,
    discover_engines,
    discover_schedulers,
    resolve_config,
)

logger = logging.getLogger("z4j.agent.fastapi.extension")

# Module-level state - there is at most one runtime per process.
_runtime: AgentRuntime | None = None


def z4j_lifespan(
    *,
    brain_url: str | None = None,
    token: str | None = None,
    project_id: str | None = None,
    celery_app: Any = None,
    hmac_secret: str | None = None,
    environment: str | None = None,
    transport: str | None = None,
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
    inner_lifespan: Callable[..., Any] | None = None,
) -> Callable[..., AsyncIterator[None]]:
    """Return a lifespan context manager that starts and stops z4j.

    This is the recommended integration pattern for FastAPI >= 0.135.
    Pass the return value directly to ``FastAPI(lifespan=...)``.

    If the application already has its own lifespan, pass it as
    ``inner_lifespan`` and z4j will wrap it::

        app = FastAPI(lifespan=z4j_lifespan(
            brain_url="...",
            token="...",
            inner_lifespan=my_existing_lifespan,
        ))

    Args:
        brain_url: URL of the z4j brain.
        token: Project-scoped bearer token.
        project_id: Project slug (default ``"default"``).
        celery_app: The Celery application instance, if using Celery.
        hmac_secret: Shared HMAC secret for command verification.
        environment: Environment label (e.g. ``"production"``).
        transport: Transport mode (``"auto"``, ``"ws"``, ``"longpoll"``).
        log_level: Agent log level.
        engines: Engine adapter names to register.
        schedulers: Scheduler adapter names to register.
        tags: Per-deployment tags.
        dev_mode: Enable development mode.
        strict_mode: Fail fast on config problems.
        autostart: Whether the runtime starts automatically.
        heartbeat_seconds: Heartbeat interval.
        buffer_path: On-disk SQLite buffer path.
        buffer_max_events: Max buffered events.
        buffer_max_bytes: Max buffer file size.
        max_payload_bytes: Per-field truncation limit.
        inner_lifespan: An existing lifespan to compose with.

    Returns:
        An async context manager suitable for ``FastAPI(lifespan=...)``.
    """
    config_kwargs: dict[str, Any] = {}
    # Collect all non-None config kwargs.
    _set_if_not_none(config_kwargs, "brain_url", brain_url)
    _set_if_not_none(config_kwargs, "token", token)
    _set_if_not_none(config_kwargs, "project_id", project_id)
    _set_if_not_none(config_kwargs, "hmac_secret", hmac_secret)
    _set_if_not_none(config_kwargs, "environment", environment)
    _set_if_not_none(config_kwargs, "transport", transport)
    _set_if_not_none(config_kwargs, "log_level", log_level)
    _set_if_not_none(config_kwargs, "engines", engines)
    _set_if_not_none(config_kwargs, "schedulers", schedulers)
    _set_if_not_none(config_kwargs, "tags", tags)
    _set_if_not_none(config_kwargs, "dev_mode", dev_mode)
    _set_if_not_none(config_kwargs, "strict_mode", strict_mode)
    _set_if_not_none(config_kwargs, "autostart", autostart)
    _set_if_not_none(config_kwargs, "heartbeat_seconds", heartbeat_seconds)
    _set_if_not_none(config_kwargs, "buffer_path", buffer_path)
    _set_if_not_none(config_kwargs, "buffer_max_events", buffer_max_events)
    _set_if_not_none(config_kwargs, "buffer_max_bytes", buffer_max_bytes)
    _set_if_not_none(config_kwargs, "max_payload_bytes", max_payload_bytes)

    @asynccontextmanager
    async def _lifespan(app: Any) -> AsyncIterator[None]:
        # Start z4j - wrapped so failures never crash the FastAPI app.
        runtime = _safe_start(config_kwargs, celery_app)

        try:
            if inner_lifespan is not None:
                async with inner_lifespan(app):
                    yield
            else:
                yield
        finally:
            # Stop z4j on shutdown.
            _safe_stop(runtime)

    return _lifespan


def install_z4j(
    app: Any,
    *,
    brain_url: str | None = None,
    token: str | None = None,
    project_id: str | None = None,
    celery_app: Any = None,
    hmac_secret: str | None = None,
    environment: str | None = None,
    transport: str | None = None,
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
) -> AgentRuntime | None:
    """Install z4j agent into a FastAPI app (manual pattern).

    This is the fallback pattern for applications that cannot use the
    lifespan approach (e.g. because of legacy code). It starts the
    runtime immediately and registers an ``atexit`` hook to stop it
    when the process exits.

    Audit H16: this path now hooks BOTH ``app.add_event_handler
    ("shutdown", ...)`` AND ``atexit``. The shutdown event handler
    is what fires under uvicorn / gunicorn's graceful SIGTERM
    handling (i.e. K8s rolling restarts); ``atexit`` is the
    fallback for processes that exit without ASGI lifespan
    teardown. Either path runs the same ``runtime.stop(...)`` so
    buffered events flush before the process dies.

    Args:
        app: The FastAPI application instance. Stored on ``app.state.z4j_runtime``
             for access by middleware or route handlers.
        brain_url: URL of the z4j brain.
        token: Project-scoped bearer token.
        project_id: Project slug.
        celery_app: The Celery application instance, if using Celery.
        hmac_secret: Shared HMAC secret for command verification.
        environment: Environment label.
        transport: Transport mode.
        log_level: Agent log level.
        engines: Engine adapter names.
        schedulers: Scheduler adapter names.
        tags: Per-deployment tags.
        dev_mode: Enable development mode.
        strict_mode: Fail fast on config problems.
        autostart: Whether the runtime starts automatically.
        heartbeat_seconds: Heartbeat interval.
        buffer_path: On-disk SQLite buffer path.
        buffer_max_events: Max buffered events.
        buffer_max_bytes: Max buffer file size.
        max_payload_bytes: Per-field truncation limit.

    Returns:
        The running AgentRuntime, or None if startup failed.
    """
    config_kwargs: dict[str, Any] = {}
    _set_if_not_none(config_kwargs, "brain_url", brain_url)
    _set_if_not_none(config_kwargs, "token", token)
    _set_if_not_none(config_kwargs, "project_id", project_id)
    _set_if_not_none(config_kwargs, "hmac_secret", hmac_secret)
    _set_if_not_none(config_kwargs, "environment", environment)
    _set_if_not_none(config_kwargs, "transport", transport)
    _set_if_not_none(config_kwargs, "log_level", log_level)
    _set_if_not_none(config_kwargs, "engines", engines)
    _set_if_not_none(config_kwargs, "schedulers", schedulers)
    _set_if_not_none(config_kwargs, "tags", tags)
    _set_if_not_none(config_kwargs, "dev_mode", dev_mode)
    _set_if_not_none(config_kwargs, "strict_mode", strict_mode)
    _set_if_not_none(config_kwargs, "autostart", autostart)
    _set_if_not_none(config_kwargs, "heartbeat_seconds", heartbeat_seconds)
    _set_if_not_none(config_kwargs, "buffer_path", buffer_path)
    _set_if_not_none(config_kwargs, "buffer_max_events", buffer_max_events)
    _set_if_not_none(config_kwargs, "buffer_max_bytes", buffer_max_bytes)
    _set_if_not_none(config_kwargs, "max_payload_bytes", max_payload_bytes)

    runtime = _safe_start(config_kwargs, celery_app)
    if runtime is not None:
        # Stash on the app so middleware/routes can reach the runtime.
        app.state.z4j_runtime = runtime
        atexit.register(_atexit_stop)

        # Audit H16: also hook the FastAPI shutdown event so SIGTERM
        # under uvicorn / gunicorn / k8s gets a clean stop with
        # buffer flush. The handler is best-effort; an exception
        # here must never block the ASGI shutdown.
        async def _on_app_shutdown() -> None:
            try:
                _safe_stop(runtime)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "z4j: error during FastAPI shutdown handler",
                )

        try:
            app.add_event_handler("shutdown", _on_app_shutdown)
        except Exception:  # noqa: BLE001
            # Some FastAPI subclasses or test doubles may not
            # support add_event_handler. Fall back to atexit only.
            logger.debug(
                "z4j: app.add_event_handler unavailable, "
                "atexit-only shutdown",
            )

    return runtime


def get_runtime() -> AgentRuntime | None:
    """Return the running agent runtime, if any.

    Used by tests and by application code that wants to flush the
    buffer manually or check the runtime state.
    """
    return _runtime


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _safe_start(
    config_kwargs: dict[str, Any],
    celery_app: Any,
) -> AgentRuntime | None:
    """Build and start the runtime, catching all errors.

    Returns the running runtime, or None if anything went wrong. Never
    raises - z4j must not crash the host application.
    """
    # Allow tests and tooling to disable the autostart entirely.
    if os.environ.get("Z4J_DISABLED", "").lower() in ("1", "true", "yes", "on"):
        logger.info("z4j: Z4J_DISABLED is set; skipping agent startup")
        return None

    global _runtime
    if _runtime is not None:
        return _runtime  # already started in this process

    try:
        runtime = _build_and_start_runtime(config_kwargs, celery_app)
    except Exception:  # noqa: BLE001
        logger.exception("z4j: failed to start agent runtime; continuing without it")
        return None

    # Cooperate with other in-process install paths (e.g. a Celery
    # worker_init signal in the same process also tries to install).
    # Whoever registered first keeps the live WebSocket; we drop our
    # freshly-built runtime if we lost the race.
    from z4j_bare._process_singleton import try_register
    active = try_register(runtime, owner="z4j_fastapi.extension")
    if active is not runtime:
        # We built + started a runtime, then lost the race. Stop
        # the local copy so we don't leak a zombie WS connection.
        try:
            runtime.stop(timeout=2.0)
        except Exception:  # noqa: BLE001
            logger.exception("z4j: error stopping duplicate runtime")
        _runtime = active
        return active

    _runtime = runtime
    logger.info("z4j: agent runtime started for fastapi")
    return runtime


def _build_and_start_runtime(
    config_kwargs: dict[str, Any],
    celery_app: Any,
) -> AgentRuntime:
    """Resolve config, discover adapters, build the runtime, start it."""
    config = resolve_config(**config_kwargs)
    framework = FastAPIFrameworkAdapter(config)
    engine_list = discover_engines(celery_app)
    scheduler_list = discover_schedulers(celery_app)

    runtime = AgentRuntime(
        config=config,
        framework=framework,
        engines=engine_list,
        schedulers=scheduler_list,
    )
    if config.autostart:
        runtime.start()
        framework.fire_startup()
    return runtime


def _safe_stop(runtime: AgentRuntime | None) -> None:
    """Stop the runtime, swallowing errors. Never raises."""
    global _runtime
    if runtime is None:
        return
    try:
        runtime.stop(timeout=5.0)
    except Exception:  # noqa: BLE001
        logger.exception("z4j: error during shutdown")
    finally:
        if _runtime is runtime:
            _runtime = None


def _atexit_stop() -> None:
    """``atexit`` handler that flushes the buffer and stops the runtime."""
    _safe_stop(_runtime)


def _set_if_not_none(d: dict[str, Any], key: str, value: Any) -> None:
    """Set ``d[key] = value`` only if ``value is not None``."""
    if value is not None:
        d[key] = value


__all__ = ["get_runtime", "install_z4j", "z4j_lifespan"]
