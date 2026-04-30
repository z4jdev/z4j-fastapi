"""FastAPI declarative scheduler reconciler (1.2.2+).

The reconciler logic lives in ``z4j_bare.declarative`` so all
framework adapters share it. FastAPI doesn't have a config object
(no ``app.config`` like Flask, no ``settings`` like Django), so
the integration is more direct: pass the schedules dict in as a
kwarg to :func:`z4j_lifespan` / :func:`install_z4j`, or call
:func:`reconcile_schedules` from your own deploy script.

The recommended pattern is reconcile-from-CI / deploy-hook, not
auto-run on app boot. Auto-run is supported (set
``reconcile_autorun=True``) but writes audit rows on every
process boot - that's fine for a single-replica dev box, costly
for an N-pod gunicorn deployment.

Programmatic example::

    from z4j_fastapi import reconcile_schedules

    reconcile_schedules(
        brain_url="https://brain.example.com",
        api_key="proj_admin_token",
        project_slug="my-project",
        z4j_schedules={
            "daily-rollup": {
                "task": "myapp.tasks.rollup",
                "kind": "cron",
                "expression": "0 3 * * *",
            },
        },
        dry_run=False,
    )
"""

from __future__ import annotations

import logging
from typing import Any

# Re-export the shared types so `from z4j_fastapi.declarative import ...`
# matches the Django/Flask surface area.
from z4j_bare.declarative import (
    ReconcileResult,
    ScheduleReconciler,
    _spec_to_brain_payload,
    _z4j_native_schedules_to_specs,
)

logger = logging.getLogger("z4j.agent.fastapi.reconcile")


def reconcile_schedules(
    *,
    brain_url: str,
    api_key: str,
    project_slug: str,
    z4j_schedules: dict[str, dict[str, Any]] | None = None,
    celery_beat_schedules: dict[str, dict[str, Any]] | None = None,
    engine: str = "celery",
    scheduler: str | None = None,
    source: str = "declarative:fastapi",
    dry_run: bool = False,
) -> ReconcileResult | None:
    """Run one reconcile pass against the brain.

    **Synchronous.** This function uses ``httpx.Client`` (sync) and
    will BLOCK the caller's event loop if invoked directly from
    async code. From an async context (a FastAPI request handler,
    a lifespan coroutine, etc.) wrap the call::

        result = await asyncio.to_thread(
            reconcile_schedules,
            brain_url=...,
            api_key=...,
            project_slug=...,
            z4j_schedules=...,
        )

    The :func:`z4j_lifespan` integration with
    ``reconcile_autorun=True`` already wraps via
    ``asyncio.to_thread`` (audit fix CRIT-6, round 1). Direct
    callers in deploy scripts / CI that run synchronously can
    invoke this function as-is.

    Returns ``None`` when no schedules are passed (silent no-op
    so we don't spam logs from a host that doesn't use the feature).

    Args:
        brain_url: e.g. ``"https://brain.example.com"``.
        api_key: project API key with ADMIN scope (needed for
            ``:import``).
        project_slug: project identifier the schedules belong to.
        z4j_schedules: dict of ``{name: {task, kind, expression, ...}}``
            in z4j-native shape.
        celery_beat_schedules: optional ``CELERY_BEAT_SCHEDULE``-shaped
            dict; entries are translated via
            :mod:`z4j_core.celerybeat_compat`. Native entries win on
            name conflict.
        engine: target engine (default ``"celery"``).
        scheduler: optional override of the project's
            ``default_scheduler_owner`` for THIS reconciler's writes.
        source: the ``source`` label written on each row. Used by
            ``mode=replace_for_source`` so the reconciler only deletes
            schedules it owns.
        dry_run: when ``True``, calls ``:diff`` and returns the diff
            without writing audit rows (useful for CI deploy gates).
    """
    if not z4j_schedules and not celery_beat_schedules:
        return None

    reconciler = ScheduleReconciler(
        brain_url=brain_url,
        api_key=api_key,
        project_slug=project_slug,
    )
    return reconciler.reconcile(
        z4j_schedules=z4j_schedules,
        celery_beat_schedules=celery_beat_schedules,
        engine=engine,
        scheduler=scheduler,
        source=source,
        dry_run=dry_run,
    )


__all__ = [
    "ReconcileResult",
    "ScheduleReconciler",
    "_spec_to_brain_payload",
    "_z4j_native_schedules_to_specs",
    "reconcile_schedules",
]
