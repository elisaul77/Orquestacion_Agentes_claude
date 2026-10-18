"""Hidden acceptance tests for the bug2-orch round (kuNNA connection map).

Copied into a run ONLY at scoring time, never before the run. Stdlib + pytest only.
KUNNA_ROOT points at the kuNNA tree under test (default /work inside the bench container).

The fixture builds a fake /proc with two containers on two Docker networks, the way Docker reports them
(the address is per network; the top-level NetworkSettings.IPAddress is empty for user-defined networks).
Both sockets of frontend -> backend are real TCP rows; nothing here is mocked except the docker client.
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(os.environ.get("KUNNA_ROOT", "/work"))
FRONT_ID = "a" * 64
BACK_ID = "b" * 64
HEADER = "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode"


def tcp_row(i, local, remote, state, inode):
    return (f"   {i}: {local} {remote} {state} 00000000:00000000 00:00000000 "
            f"00000000     0        0 {inode} 1 0000000000000000 100 0 10 0\n")


@pytest.fixture
def netmap(monkeypatch):
    sys.path.insert(0, str(ROOT / "backend"))
    import netmap as module
    module._cache.update(at=0.0, data=None)
    yield module
    module._cache.update(at=0.0, data=None)


class FakeContainer:
    def __init__(self, name, cid, pid, networks):
        self.name, self.id = name, cid
        self.attrs = {
            "NetworkSettings": {"Networks": networks, "Ports": {}},
            "HostConfig": {"NetworkMode": "kunna_net"},
            "State": {"Pid": pid},
        }


class FakeDocker:
    def __init__(self, containers):
        self.containers = self
        self._containers = containers

    def list(self):
        return self._containers


@pytest.fixture
def proc_and_client(netmap, tmp_path, monkeypatch):
    """frontend (pid 1001) connects to backend (pid 1002) over the data network."""
    root = tmp_path / "proc"
    frontend_rows = [tcp_row(0, "020013AC:9C40", "030013AC:1F40", "01", 101)]          # 172.19.0.2:40000 -> 172.19.0.3:8000
    backend_rows = [tcp_row(0, "00000000:1F40", "00000000:0000", "0A", 200),           # listening :8000
                    tcp_row(1, "030013AC:1F40", "020013AC:9C40", "01", 201)]           # accepted from frontend
    layout = {1001: (frontend_rows, [101], 2001), 1002: (backend_rows, [200, 201], 2002)}
    for pid, (rows, inodes, netns) in layout.items():
        base = root / str(pid)
        (base / "net").mkdir(parents=True)
        (base / "ns").mkdir()
        (base / "fd").mkdir()
        (base / "cgroup").write_text(f"0::/system.slice/docker-{FRONT_ID if pid == 1001 else BACK_ID}.scope\n")
        os.symlink(f"net:[{netns}]", base / "ns" / "net")
        (base / "net" / "tcp").write_text(HEADER + "\n" + "".join(rows))
        for k, ino in enumerate(inodes):
            os.symlink(f"socket:[{ino}]", base / "fd" / str(k))
    monkeypatch.setattr(netmap, "HOST_PROC", str(root))
    kunna_net = {"IPAddress": "172.18.0.2", "Gateway": "172.18.0.1"}
    data_front = {"IPAddress": "172.19.0.2", "Gateway": "172.19.0.1"}
    back_net = {"IPAddress": "172.18.0.3", "Gateway": "172.18.0.1"}
    data_back = {"IPAddress": "172.19.0.3", "Gateway": "172.19.0.1"}
    client = FakeDocker([
        FakeContainer("kunna-frontend", FRONT_ID, 1001, {"kunna_net": kunna_net, "data_net": data_front}),
        FakeContainer("kunna-backend", BACK_ID, 1002, {"kunna_net": back_net, "data_net": data_back}),
    ])
    return client


def test_frontend_to_backend_is_drawn_once_as_an_internal_link(netmap, proc_and_client):
    edges = netmap.collect(proc_and_client)["edges"]
    internal = [e for e in edges
                if (e["source"], e["target"], e["kind"]) == ("kunna-frontend", "kunna-backend", "internal")]
    assert len(internal) == 1, edges
    assert internal[0]["count"] == 1, edges


def test_no_external_or_host_link_between_the_two_containers(netmap, proc_and_client):
    edges = netmap.collect(proc_and_client)["edges"]
    names = {"kunna-frontend", "kunna-backend"}
    wrong = [e for e in edges if e["kind"] in ("external", "host")
             and (e["source"] in names or e["target"] in names)]
    assert wrong == [], wrong
