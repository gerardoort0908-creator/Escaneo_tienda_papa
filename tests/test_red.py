import pytest

from app.red import es_ip_local, ip_en_la_red


@pytest.mark.parametrize("ip", ["192.168.1.10", "10.0.0.4", "172.20.1.1"])
def test_ips_de_casa(ip):
    assert es_ip_local(ip)


@pytest.mark.parametrize("ip", ["127.0.0.1", "8.8.8.8", "169.254.3.3", "basura", "::1"])
def test_ips_que_no_sirven(ip):
    assert not es_ip_local(ip)


def test_siempre_regresa_una_ip_usable():
    ip = ip_en_la_red()
    assert ip == "127.0.0.1" or es_ip_local(ip)
