# z4j-fastapi

[![PyPI version](https://img.shields.io/pypi/v/z4j-fastapi.svg)](https://pypi.org/project/z4j-fastapi/)
[![Python](https://img.shields.io/pypi/pyversions/z4j-fastapi.svg)](https://pypi.org/project/z4j-fastapi/)
[![License](https://img.shields.io/pypi/l/z4j-fastapi.svg)](https://github.com/z4jdev/z4j-fastapi/blob/main/LICENSE)

The FastAPI framework adapter for [z4j](https://z4j.com).

Adds the z4j agent into your FastAPI app via a single `add_z4j(app)`
call. Auto-discovers the engine adapter you have installed (Celery,
RQ, Dramatiq, Huey, arq, TaskIQ) and streams every task lifecycle
event to z4j. Operator control actions flow back the same
channel.

## What it ships

- **One-line install**, `add_z4j(app)` and the agent connects on the
  next uvicorn worker boot
- **Engine auto-discovery**, picks up whichever z4j engine adapter
  is installed alongside; cross-stack combos (FastAPI + arq,
  FastAPI + Celery) are first-class
- **`@z4j_meta` decorator**, optional per-task annotations
  (`priority="critical"`, `description="..."`) for dashboard
  filtering and SLO display
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
from z4j_fastapi import add_z4j

app = FastAPI()
add_z4j(app)  # reads Z4J_AGENT_TOKEN, Z4J_BRAIN_URL, Z4J_PROJECT from env
```

Mint the agent token from the dashboard's Agents page.

## Reliability

- No exception from the agent ever propagates back into FastAPI
  request handlers or your worker code.
- Events buffer locally when z4j is unreachable; your application
  never blocks on network I/O.

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
