# z4j-fastapi

[![PyPI version](https://img.shields.io/pypi/v/z4j-fastapi.svg)](https://pypi.org/project/z4j-fastapi/)
[![Python](https://img.shields.io/pypi/pyversions/z4j-fastapi.svg)](https://pypi.org/project/z4j-fastapi/)
[![License](https://img.shields.io/pypi/l/z4j-fastapi.svg)](https://github.com/z4jdev/z4j-fastapi/blob/main/LICENSE)

The FastAPI framework adapter for [z4j](https://z4j.com).

Adds the z4j agent to a FastAPI app through `z4j_lifespan(...)` passed to
`FastAPI(lifespan=...)`. Register engines by passing their native handles
(`celery_app=`, `rq_app=`, `huey=`, and so on); installing an adapter package
alone does not select it. Dramatiq is the exception only when its process-global
broker already has registered actors.

## Compatibility

- FastAPI 0.109.1+ (no upper cap)
- Python 3.11+

Pair with an engine adapter (`z4j-celery`, `z4j-rq`, `z4j-dramatiq`, `z4j-huey`, `z4j-arq`, `z4j-taskiq`); each engine adapter carries its own upstream floor.

Full per-adapter matrix at <https://z4j.dev/reference/compatibility/>.

## What it ships

- **One-line install**, pass `z4j_lifespan(...)` to
  `FastAPI(lifespan=...)` and the agent connects on the next uvicorn
  worker boot
- **Explicit engine registration**, supports multiple native engine handles in
  one process; adapter installation without the corresponding handle is skipped
- **Loop-safe TaskIQ discovery**, `taskiq_broker=` attaches z4j middleware;
  TaskIQ broker startup records the actual owner loop
- **Per-task metadata from supporting engine adapters**; `z4j-celery`,
  `z4j-rq`, and `z4j-dramatiq` expose `@z4j_meta` rather than this framework
  package defining one
- **Service-user safe**, auto-relocates the local outbound buffer
  to `$TMPDIR/z4j-{uid}` when `$HOME` is unwritable (uvicorn under
  a service account, distroless images, etc.)

## Install

```bash
pip install z4j-fastapi z4j-celery z4j-celerybeat
```

Wire it into your app:

```python
from fastapi import FastAPI
from myproject.celery import app as celery_app
from z4j_fastapi import z4j_lifespan

# reads Z4J_TOKEN, Z4J_HMAC_SECRET, Z4J_BRAIN_URL, Z4J_PROJECT_ID from env
app = FastAPI(lifespan=z4j_lifespan(celery_app=celery_app))
```

Pass explicit config as kwargs
(`z4j_lifespan(brain_url=..., token=..., project_id=..., hmac_secret=...)`)
instead of env vars if you prefer. Apps that already own their lifespan can wrap
it via `inner_lifespan=`; apps that cannot use lifespan at all can
call `install_z4j(app)` instead.

With `taskiq_broker=`, both installation forms attach z4j's middleware but do
not assume that FastAPI's ambient loop owns the supplied broker. TaskIQ's later
broker startup binds the real owner loop. Until that binding occurs, TaskIQ
submit and result probes fail closed. Attach before host startup; if the broker
was already started elsewhere, use the direct adapter API and pass its verified
live `broker_loop` explicitly.

Mint the agent from the dashboard's Agents page and retain both values it shows:
the bearer token and the HMAC secret.

## Reliability

- Agent startup and delivery failures are logged and isolated from FastAPI
  request handlers and worker code; capture hooks make no brain network request
  inline.
- Engine event queues and the SQLite outbound buffer are bounded. Queue
  overflow drops new events and buffer pressure evicts oldest rows; both losses
  are logged.

## Documentation

Full docs at [z4j.dev/frameworks/fastapi/](https://z4j.dev/frameworks/fastapi/).

## License

Apache-2.0, see [LICENSE](LICENSE).

## Links

- Homepage: https://z4j.com
- Documentation: https://z4j.dev
- PyPI: https://pypi.org/project/z4j-fastapi/
- Issues: https://github.com/z4jdev/z4j-fastapi/issues
- Changelog: [CHANGELOG.md](CHANGELOG.md)
- Security: security@z4j.com (see [SECURITY.md](SECURITY.md))
