# z4j-fastapi

[![PyPI version](https://img.shields.io/pypi/v/z4j-fastapi.svg)](https://pypi.org/project/z4j-fastapi/)
[![Python](https://img.shields.io/pypi/pyversions/z4j-fastapi.svg)](https://pypi.org/project/z4j-fastapi/)
[![License](https://img.shields.io/pypi/l/z4j-fastapi.svg)](https://github.com/z4jdev/z4j-fastapi/blob/main/LICENSE)


**License:** Apache 2.0

FastAPI framework adapter for [z4j](https://z4j.com). Integrates via
FastAPI's lifespan hook - one context manager wraps the agent's lifecycle
with your app's startup and shutdown.

## Install

Pick your task engine and install with the matching extra. Each extra
pulls the engine adapter AND its companion scheduler in one shot, so
a fresh install never needs a second command.

```bash
pip install z4j-fastapi[arq]        # arq + arq-cron (async-native, recommended)
pip install z4j-fastapi[taskiq]     # TaskIQ + taskiq-scheduler (async, broker-flexible)
pip install z4j-fastapi[celery]     # Celery + celery-beat (sync stack)
pip install z4j-fastapi[rq]         # RQ + rq-scheduler
pip install z4j-fastapi[dramatiq]   # Dramatiq + APScheduler
pip install z4j-fastapi[huey]       # Huey + huey-periodic
pip install z4j-fastapi[all]        # every engine (CI / kitchen sink)
```

`pip install z4j-fastapi` (no extra) installs only the framework adapter.
That's useful if you already manage engine packages elsewhere; otherwise
always pick an engine extra.

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
