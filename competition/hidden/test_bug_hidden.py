"""Hidden acceptance tests for the bug round (kuNNA netmap).

Copied into a run ONLY at scoring time, never before the run. Stdlib + pytest only.
KUNNA_ROOT points at the kuNNA tree under test (default /work inside the bench container).
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(os.environ.get("KUNNA_ROOT", "/work"))


@pytest.fixture(scope="module")
def netmap():
    sys.path.insert(0, str(ROOT / "backend"))
    import netmap as module
    return module


def test_ipv4_addresses_decode_from_proc_little_endian(netmap):
    # /proc/net/tcp stores IPv4 as a little-endian u32: 172.18.0.2:80 -> 020012AC:0050
    assert netmap._hex_to_addr("020012AC:0050") == ("172.18.0.2", 80)
    assert netmap._hex_to_addr("0100007F:1F90") == ("127.0.0.1", 8080)


def test_ipv4_mapped_ipv6_still_decodes(netmap):
    # ::ffff:127.0.0.1 in the four-word little-endian layout of tcp6
    assert netmap._hex_to_addr("0000000000000000FFFF00000100007F:1F90") == ("127.0.0.1", 8080)


def test_read_tcp_yields_real_addresses(netmap, tmp_path, monkeypatch):
    header = "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode"
    line = ("   0: 020012AC:9C40 0100A8C0:0050 01 00000000:00000000 00:00000000 "
            "00000000     0        0 12345 1 0000000000000000 100 0 10 0")
    (tmp_path / "42" / "net").mkdir(parents=True)
    (tmp_path / "42" / "net" / "tcp").write_text(header + "\n" + line + "\n")
    monkeypatch.setattr(netmap, "HOST_PROC", str(tmp_path))
    rows = list(netmap._read_tcp(42))
    local, remote, state, inode = rows[0]
    assert local == ("172.18.0.2", 40000)
    assert remote == ("192.168.0.1", 80)
    assert state == "01"
    assert inode == "12345"
