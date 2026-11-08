"""Small, dependency-free logging bootstrap for the GUI and CLI."""

from __future__ import annotations

import logging
import os
import sys

LOGGER_NAME = "atk_control"
_configured = False


def configure(debug: bool = False) -> None:
    """Configure package logging once.

    The GUI is normally started from a desktop session, so stderr is captured
    by the journal.  ``--debug`` or ``ATK_CONTROL_DEBUG=1`` raises verbosity.
    """
    global _configured
    logger = logging.getLogger(LOGGER_NAME)
    if debug or os.environ.get("ATK_CONTROL_DEBUG", "").lower() in ("1", "true", "yes"):
        logger.setLevel(logging.DEBUG)
    elif not _configured:
        logger.setLevel(logging.INFO)

    if not _configured:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        logger.addHandler(handler)
        logger.propagate = False
        _configured = True
