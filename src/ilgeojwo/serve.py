"""`make run`: mint a pairing token, show the QR, serve on the LAN.

The token exists because the server must listen on 0.0.0.0 for her phone to reach
it, and /scans returns the full OCR text of every document she has scanned. Korean
share-houses commonly put every unit on one subnet.
"""

from __future__ import annotations

import os
import secrets
import sys

from .env import FILENAME, load_env_file
from .lan import pairing_url, print_qr


def main() -> int:
    import pathlib

    import uvicorn

    # Whatever ./setup.sh or setup.ps1 chose for this machine.
    load_env_file(pathlib.Path(FILENAME), os.environ)

    port = int(os.environ.get("ILGEOJWO_PORT", "8000"))
    token = os.environ.get("ILGEOJWO_TOKEN") or secrets.token_urlsafe(9)
    os.environ["ILGEOJWO_TOKEN"] = token

    print_qr(pairing_url(port, token))
    print("  This link is the key. Anyone on this network who has it can read")
    print("  every scan you have made, so do not post it anywhere.\n")

    uvicorn.run("ilgeojwo.web.wire:app", factory=True, host="0.0.0.0", port=port,
                log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
