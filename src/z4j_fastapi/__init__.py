"""z4j-fastapi - FastAPI framework adapter for z4j.

Public API:

- :func:`z4j_lifespan` - returns a lifespan context manager that starts
  and stops the z4j agent. Pass it to ``FastAPI(lifespan=...)``.
- :func:`install_z4j` - manual install for apps that cannot use lifespan.
- :func:`get_runtime` - retrieve the running agent runtime.
- :class:`FastAPIFrameworkAdapter` - the framework adapter implementation.

Typical usage (lifespan, recommended)::

    from fastapi import FastAPI
    from z4j_fastapi import z4j_lifespan

    app = FastAPI(lifespan=z4j_lifespan(
        brain_url="http://localhost:7700",
        token="your-token",
    ))

Licensed under Apache License 2.0.
"""

from __future__ import annotations

from z4j_fastapi.extension import get_runtime, install_z4j, z4j_lifespan
from z4j_fastapi.framework import FastAPIFrameworkAdapter

# Importing ``z4j_celery`` (if installed) registers the Celery
# ``worker_init`` signal handler that auto-bootstraps the agent
# inside Celery worker processes. Without this, FastAPI apps that
# run their Celery workers via ``celery -A app:celery_app worker``
# never register as z4j agents - the lifespan only fires under
# uvicorn, not under the Celery worker command.
#
# This mirrors the Django AppConfig's auto-bootstrap behaviour so
# FastAPI workers are first-class citizens in the agent registry.
# If z4j_celery is not installed, the import is silently skipped
# and nothing changes.
try:
    import z4j_celery  # noqa: F401  (imported for its side-effects)
except ImportError:
    pass

__version__ = "1.0.0"

__all__ = [
    "FastAPIFrameworkAdapter",
    "__version__",
    "get_runtime",
    "install_z4j",
    "z4j_lifespan",
]
