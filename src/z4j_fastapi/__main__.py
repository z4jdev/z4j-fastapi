"""``python -m z4j_fastapi`` - module entry point.

Both forms work and dispatch to the same code:

    z4j-fastapi <subcommand>            # pip-installed console script
    python -m z4j_fastapi <subcommand>  # module form

The module form is what containerized deploys typically use;
the console-script form is what humans type. Both supported in
1.1.2+.
"""

from __future__ import annotations

import sys

from z4j_fastapi.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
