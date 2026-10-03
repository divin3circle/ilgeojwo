"""Find the LAN address and show a QR code, so her phone joins in one scan."""

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


def print_qr(url: str) -> None:
    import qrcode

    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make()
    qr.print_ascii(invert=True)
    print(f"\n  Point her phone camera at this, or open:  {url}\n")
    if "127.0.0.1" in url:
        print("  WARNING: that is a loopback address. This laptop is not on WiFi,")
        print("  so her phone cannot reach it. Join a network and restart.\n")
