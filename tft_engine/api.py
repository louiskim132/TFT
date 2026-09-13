"""Minimal HTTP service exposing the decision engine.

Stdlib-only (http.server) — the live path stays dependency-free.

    POST /decision          {"state": {...}, "max_actions": 3}
    GET  /health
    GET  /knowledge/status

Run:  python -m tft_engine.api --db data/tft.db --port 8080
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .engine import DecisionEngine
from .state_io import StateValidationError, game_state_from_dict
from .stats import StatsProvider


def _feature_contributions(scored) -> dict[str, float]:
    return {f.name: round(f.contribution, 4) for f in scored.features}


def decision_response(engine: DecisionEngine, payload: dict[str, Any]) -> dict[str, Any]:
    state = game_state_from_dict(payload.get("state", payload))
    max_actions = int(payload.get("max_actions", 3))
    if max_actions < 1:
        raise StateValidationError("max_actions must be >= 1")
    result = engine.decide(state)
    actions = result.actions[:max_actions]
    if not actions:
        return {
            "recommended_action": None,
            "alternatives": [],
            "confidence": 0.0,
            "latency_ms": result.latency_ms,
            "reasons": ["no candidate actions"],
            "feature_contributions": {},
        }
    top = actions[0]
    return {
        "recommended_action": asdict(top),
        "alternatives": [asdict(a) for a in actions[1:]],
        "confidence": top.confidence,
        "latency_ms": result.latency_ms,
        "candidate_count": result.candidate_count,
        "reasons": top.reasons,
        "feature_contributions": _feature_contributions(top),
    }


def _knowledge_status(provider: StatsProvider) -> dict[str, Any]:
    status_fn = getattr(provider, "knowledge_status", None)
    if callable(status_fn):
        return status_fn()
    return {"provider": type(provider).__name__, "snapshots": []}


def make_handler(engine: DecisionEngine, provider: StatsProvider):
    class Handler(BaseHTTPRequestHandler):
        def _json(self, code: int, body: dict[str, Any]) -> None:
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._json(200, {"status": "ok"})
            elif self.path == "/knowledge/status":
                self._json(200, _knowledge_status(provider))
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/decision":
                self._json(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, json.JSONDecodeError):
                self._json(400, {"error": "malformed JSON body"})
                return
            try:
                self._json(200, decision_response(engine, payload))
            except StateValidationError as e:
                self._json(400, {"error": str(e)})
            except Exception as e:  # never leak a stack trace over HTTP
                self._json(500, {"error": f"internal error: {type(e).__name__}"})

        def log_message(self, *args: object) -> None:
            pass  # quiet by default

    return Handler


def create_server(
    provider: StatsProvider,
    host: str = "127.0.0.1",
    port: int = 8080,
) -> ThreadingHTTPServer:
    # Engine keeps a generous cap; per-request max_actions slices the output.
    engine = DecisionEngine(provider, max_results=64)
    return ThreadingHTTPServer((host, port), make_handler(engine, provider))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tft_engine.api")
    ap.add_argument("--db", default=None, help="sqlite knowledge db; omit for fixture data")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args(argv)

    if args.db:
        from .sqlite_provider import SQLiteStatsProvider

        provider: StatsProvider = SQLiteStatsProvider(args.db)
    else:
        from .fixtures import build_fixture_snapshot
        from .stats import InMemoryStatsProvider

        provider = InMemoryStatsProvider.from_snapshot(build_fixture_snapshot())

    server = create_server(provider, host=args.host, port=args.port)
    print(f"serving on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
