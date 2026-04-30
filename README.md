# z4j-fastapi

[![PyPI version](https://img.shields.io/pypi/v/z4j-fastapi.svg)](https://pypi.org/project/z4j-fastapi/)
[![Python](https://img.shields.io/pypi/pyversions/z4j-fastapi.svg)](https://pypi.org/project/z4j-fastapi/)
[![License](https://img.shields.io/pypi/l/z4j-fastapi.svg)](https://github.com/z4jdev/z4j-fastapi/blob/main/LICENSE)

The FastAPI framework adapter for [z4j](https://z4j.com).

Adds the z4j agent into your FastAPI app via a single
`add_z4j(app)` call. Auto-discovers the engine adapter you have
installed (Celery, RQ, Dramatiq, Huey, arq, TaskIQ) and streams
every task lifecycle event to the brain.

## Install

```bash
pip install z4j-fastapi z4j-celery z4j-celerybeat
```

## Documentation

Full docs at [z4j.dev/frameworks/fastapi/](https://z4j.dev/frameworks/fastapi/).

## License

Apache-2.0 — see [LICENSE](LICENSE).

## Links

- Homepage: https://z4j.com
- Documentation: https://z4j.dev
- PyPI: https://pypi.org/project/z4j-fastapi/
- Issues: https://github.com/z4jdev/z4j-fastapi/issues
- Changelog: [CHANGELOG.md](CHANGELOG.md)
- Security: security@z4j.com (see [SECURITY.md](SECURITY.md))
