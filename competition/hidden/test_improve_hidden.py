"""Hidden acceptance tests for the improve round (kuNNA TOTP login).

Copied into a run ONLY at scoring time. Checks behaviour through POST /api/auth/login,
not implementation details: thresholds and lock length are free choices within the prompt.
Needs fastapi + httpx (kuNNA backend deps, installed in the bench image).
KUNNA_ROOT points at the kuNNA tree under test (default /work inside the bench container).

Clock: a lockout may be built on time.time OR time.monotonic OR time.perf_counter. The `clock` fixture
moves all three by the same offset, so a 24 h jump is seen by whichever clock the implementation reads.
"""
import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(os.environ.get("KUNNA_ROOT", "/work"))


@pytest.fixture(autouse=True)
def fast_sleep(monkeypatch):
    # the existing 1 s brute-force delay is not under test: stub time.sleep on the time module itself
    monkeypatch.setattr(time, "sleep", lambda s: None)


@pytest.fixture
def clock(monkeypatch):
    """advance(seconds): moves time.time, time.monotonic and time.perf_counter together."""
    offset = {"s": 0.0}
    real_time, real_mono, real_perf = time.time, time.monotonic, time.perf_counter
    monkeypatch.setattr(time, "time", lambda: real_time() + offset["s"])
    monkeypatch.setattr(time, "monotonic", lambda: real_mono() + offset["s"])
    monkeypatch.setattr(time, "perf_counter", lambda: real_perf() + offset["s"])

    def advance(seconds):
        offset["s"] += seconds
    return advance


@pytest.fixture
def env(tmp_path, monkeypatch, clock):
    # auth.py keeps its secret under ./data relative to the cwd: use a scratch cwd
    monkeypatch.chdir(tmp_path)
    sys.path.insert(0, str(ROOT / "backend"))
    sys.modules.pop("auth", None)
    import auth
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(auth.router)
    app.middleware("http")(auth.require_auth)
    getattr(auth, "sessions", {}).clear()
    return auth, TestClient(app), clock


def good_code(auth):
    return auth.totp_at(int(time.time() // 30))


def bad_codes(auth, n=40):
    valid = {auth.totp_at(int(time.time() // 30) + d) for d in (-1, 0, 1)}
    out = []
    for i in range(1_000_000):
        code = f"{i:06d}"
        if code not in valid:
            out.append(code)
            if len(out) == n:
                break
    return out


def login(client, code):
    return client.post("/api/auth/login", json={"code": code})


def test_correct_code_still_logs_in(env):
    auth, client, _ = env
    r = login(client, good_code(auth))
    assert r.status_code == 200
    assert "token" in r.json()


def test_two_wrong_codes_do_not_lock_out_the_owner(env):
    auth, client, _ = env
    codes = bad_codes(auth)
    for code in codes[:2]:
        assert login(client, code).status_code == 401
    assert login(client, good_code(auth)).status_code == 200


def test_repeated_wrong_codes_get_429_after_a_bounded_number(env):
    auth, client, _ = env
    statuses = [login(client, code).status_code for code in bad_codes(auth)]
    assert 429 in statuses, f"no lockout after 40 wrong codes: {statuses}"
    first = statuses.index(429)
    assert first <= 10, f"lockout only after {first} wrong codes (limit: 10)"
    assert set(statuses[:first]) == {401}


def test_lockout_also_refuses_the_correct_code(env):
    auth, client, _ = env
    for code in bad_codes(auth):
        login(client, code)
    assert login(client, good_code(auth)).status_code == 429


def test_lockout_is_temporary(env):
    auth, client, clock = env
    for code in bad_codes(auth):
        login(client, code)
    clock(24 * 3600)
    assert login(client, good_code(auth)).status_code == 200
