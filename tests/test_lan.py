import re

from ilgeojwo.lan import lan_url


def test_lan_url_formats_a_routable_address():
    """Host discovery is injected, so this never depends on the network."""
    assert lan_url(8000, host="192.168.1.42") == "http://192.168.1.42:8000"


def test_discovery_yields_an_address_shaped_url():
    """Must hold offline too (Global Constraint), so it asserts shape, not
    reachability. If it prints 127.0.0.1 she simply is not on WiFi — `make run`
    says so rather than this test failing."""
    assert re.match(r"^http://\d+\.\d+\.\d+\.\d+:8000$", lan_url(8000))
