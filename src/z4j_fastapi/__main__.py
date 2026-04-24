"""``python -m z4j_fastapi`` - FastAPI-tagged wrapper around z4j-bare's CLI.

Usage::

    python -m z4j_fastapi doctor
    python -m z4j_fastapi doctor --json

Subcommands are delegated 1:1 to ``python -m z4j_bare`` which
already understands ``Z4J_*`` env vars and runs the same probe
ladder. The wrapper exists for ergonomic parity with z4j-django's
``manage.py z4j_doctor`` and z4j-flask's ``python -m z4j_flask
doctor``.

Future work: expose ``--app PATH:VAR`` to import the FastAPI app
and read any framework-side overrides (rare; most operators just
use env vars).
"""

from __future__ import annotations

import sys

from z4j_bare.cli import main


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
