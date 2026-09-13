import json
import threading
import urllib.request

import pytest

from tft_engine.api import create_server
from tft_engine.fixtures import build_fixture_snapshot
from tft_engine.sqlite_provider import SQLiteStatsProvider
from tft_engine.stats import InMemoryStatsProvider


@pytest.fixture()
def server(tmp_path):
    provider = SQLiteStatsProvider(tmp_path / "k.db")
    provider.apply_snapshot(build_fixture_snapshot())
    srv = create_server(provider, port=0)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()
    provider.close()


def _post(url: str, body: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_health(server) -> None:
    with urllib.request.urlopen(f"{server}/health", timeout=5) as resp:
        assert resp.status == 200
        assert json.loads(resp.read())["status"] == "ok"


def test_knowledge_status(server) -> None:
    with urllib.request.urlopen(f"{server}/knowledge/status", timeout=5) as resp:
        body = json.loads(resp.read())
    assert body["snapshots"][0]["compositions"] == 4


def test_decision_endpoint(server) -> None:
    code, body = _post(
        f"{server}/decision",
        {
            "state": {
                "patch": "15.5", "stage": "3-5", "hp": 50, "gold": 30, "level": 6,
                "board": [{"name": "Vi", "star_level": 2}, {"name": "Warwick"}],
                "shop": [{"name": "DrMundo", "cost": 4}],
            },
            "max_actions": 3,
        },
    )
    assert code == 200
    assert body["recommended_action"] is not None
    assert len(body["alternatives"]) <= 2
    assert "confidence" in body
    assert "latency_ms" in body
    assert "feature_contributions" in body
    assert body["reasons"]


def test_decision_rejects_bad_state(server) -> None:
    code, body = _post(f"{server}/decision", {"state": {"patch": "15.5"}})
    assert code == 400
    assert "error" in body


def test_unknown_route_404(server) -> None:
    try:
        urllib.request.urlopen(f"{server}/nope", timeout=5)
        raise AssertionError("expected 404")
    except urllib.error.HTTPError as e:
        assert e.code == 404
