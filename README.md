# z4j-fastapi

[![PyPI version](https://img.shields.io/pypi/v/z4j-fastapi.svg)](https://pypi.org/project/z4j-fastapi/)
[![Python](https://img.shields.io/pypi/pyversions/z4j-fastapi.svg)](https://pypi.org/project/z4j-fastapi/)
[![License](https://img.shields.io/pypi/l/z4j-fastapi.svg)](https://github.com/z4jdev/z4j-fastapi/blob/main/LICENSE)


**License:** Apache 2.0
**Status:** v1.0.0 - first public release.

FastAPI framework adapter for [z4j](https://z4j.com). Integrates via
FastAPI's lifespan hook - one context manager wraps the agent's lifecycle
with your app's startup and shutdown.

## Install

```bash
# FastAPI + arq (the most common async-native pairing)
pip install z4j-fastapi z4j-arq z4j-arqcron

# FastAPI + Celery (when the sync stack is preferred)
pip install z4j-fastapi z4j-celery z4j-celerybeat

# FastAPI + Dramatiq / RQ / Huey / taskiq - all supported
pip install z4j-fastapi z4j-dramatiq z4j-apscheduler
pip install z4j-fastapi z4j-taskiq z4j-taskiqscheduler
```

## Configure

Mount the z4j lifespan in your FastAPI app:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from z4j_fastapi import Z4JLifespan

z4j = Z4JLifespan(
    brain_url="https://z4j.internal",
    token="z4j_agent_...",        # minted in the brain dashboard
    project_id="my-project",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with z4j(app):
        yield

app = FastAPI(lifespan=lifespan)
```

Or, if you have no other lifespan logic:

```python
from z4j_fastapi import Z4JLifespan

app = FastAPI(lifespan=Z4JLifespan(
    brain_url="https://z4j.internal",
    token="z4j_agent_...",
    project_id="my-project",
))
```

On `uvicorn` startup the agent connects to the brain and z4j's dashboard
populates with every arq / Celery / Dramatiq / taskiq / Huey task your
workers register.

## What it does

| Piece | Purpose |
|---|---|
| `Z4JLifespan(...)` | Async context manager matching FastAPI's lifespan contract |
| Graceful shutdown | Flushes the event buffer on `await lifespan.aclose()` |
| Async-native | Uses `asyncio.create_task` - never blocks the event loop |

## Reliability

`z4j-fastapi` follows the project-wide safety rule: **z4j never breaks
your FastAPI app**. Agent failures are caught at the boundary and never
propagate into your request handlers.

## Documentation

- [Quickstart (FastAPI)](https://z4j.dev/getting-started/quickstart-fastapi/)
- [Install guide](https://z4j.dev/getting-started/install/)
- [Architecture](https://z4j.dev/concepts/architecture/)

## License

Apache 2.0 - see [LICENSE](LICENSE). Your FastAPI application is never
AGPL-tainted by importing `z4j_fastapi`.

## Links

- Homepage: <https://z4j.com>
- Documentation: <https://z4j.dev>
- Issues: <https://github.com/z4jdev/z4j-fastapi/issues>
- Changelog: [CHANGELOG.md](CHANGELOG.md)
- Security: `security@z4j.com` (see [SECURITY.md](SECURITY.md))
