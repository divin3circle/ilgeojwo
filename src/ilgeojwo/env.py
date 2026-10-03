"""A tiny settings file, so `setup` and `run` cannot disagree.

Her laptop is Windows with 16 GB and a graphics card, so setup picks a larger
model than the 8 GB machine this was written on. Without somewhere to record that
choice, setup would pull one model and the server would load another.
"""

from __future__ import annotations

from pathlib import Path
from typing import MutableMapping

FILENAME = ".ilgeojwo.env"


def load_env_file(path: Path, env: MutableMapping[str, str]) -> None:
    """Fills in anything `env` does not already define. Never raises."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if not key:
            continue
        # The real environment always wins, so a deliberate override on the
        # command line is never silently undone by a stale file.
        env.setdefault(key, value)
