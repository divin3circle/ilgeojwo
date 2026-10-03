"""Find the LAN address and show a QR code, so a phone joins in one scan."""

from __future__ import annotations

import socket


def _discover_host() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))  # no packet is sent; this only picks a route
        return str(sock.getsockname()[0])
    except OSError:
        return socket.gethostbyname(socket.gethostname())
    finally:
        sock.close()


def lan_url(port: int, host: str | None = None) -> str:
    return f"http://{host or _discover_host()}:{port}"


def pairing_url(port: int, token: str | None, host: str | None = None) -> str:
    base = f"{lan_url(port, host)}/"
    return f"{base}?t={token}" if token else base


def print_qr(url: str) -> None:
    import qrcode

    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make()
    qr.print_ascii(invert=True)
    # Flushed because logging writes to stderr while this writes to stdout: when
    # the output is redirected to a file, an unflushed line arrives out of order
    # or is lost entirely if the process is killed.
    print(f"\n  Scan this with your phone camera, or open:  {url}\n", flush=True)
    if "127.0.0.1" in url:
        print("  WARNING: that is a loopback address. This laptop is not on WiFi,")
        print("  so a phone cannot reach it. Join a WiFi network and restart.\n",
              flush=True)
