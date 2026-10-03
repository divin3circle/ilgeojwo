"""Operational logging that cannot leak what was scanned.

The tool's claim is that documents stay on this machine. A log file is still on
this machine, but it is the one place content escapes by habit — pasted into a
bug report, caught in a screenshot, copied out of a terminal. So the log records
shapes and timings only: how long, how much, what happened. Never the text.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger("ilgeojwo")


@dataclass(frozen=True)
class ScanEvent:
    lens: str
    status: str
    ocr_ms: int
    llm_ms: int
    ocr_chars: int
    warnings: int
    approximate: int


def log_scan(event: ScanEvent) -> None:
    line = (
        f"scan lens={event.lens} status={event.status} "
        f"ocr={event.ocr_ms}ms llm={event.llm_ms}ms chars={event.ocr_chars} "
        f"warnings={event.warnings} approximate={event.approximate}"
    )
    if event.status == "ok":
        log.info(line)
    else:
        log.warning(line)


def configure(level: int = logging.INFO) -> None:
    """Quiet, single-line output. Called by the launcher, never on import."""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))
    log.handlers[:] = [handler]
    log.setLevel(level)
    log.propagate = False
