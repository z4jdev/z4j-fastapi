"""z4j-fastapi CLI: ``z4j-fastapi <subcommand>`` and ``python -m z4j_fastapi``.

Inherits the full doctor/check/status/restart surface from
``z4j_bare.cli``. ``--adapter`` is pre-filled to ``fastapi`` for
``restart``/``reload`` so SIGHUP routes to the fastapi agent's
pidfile.

Subcommand summary (all inherited):

- ``doctor`` - full probe ladder + JSON output option
- ``check`` - compact pass/fail
- ``status`` - one-line current state
- ``restart`` / ``reload`` - SIGHUP the fastapi agent's pidfile
- ``run``, ``version`` - inherited verbatim from z4j-bare
"""

from __future__ import annotations

from z4j_bare.cli import make_main_for_adapter

main = make_main_for_adapter("fastapi")


__all__ = ["main"]
