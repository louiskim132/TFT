"""MetaBot.GG adapter — live TFT comp priors via their public MCP endpoint.

MetaBot.GG exposes a read-only streamable-HTTP MCP server (no auth, ~60
req/min). `get_team_comp` returns structured comp entries: name, tier,
win/pick rates, avg placement, and a URL that encodes the comp's unit
apiNames — which we resolve to canonical unit names via the Community Dragon
catalog.

Caveat: MetaBot does not publish per-comp sample sizes. We assign a nominal
N (AGGREGATE_PSEUDO_N) so shrinkage weights real data ~4:1 over the prior —
documented, tunable, never treated as exact.
"""

from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timezone
from typing import Any

from ..stats import CompStats, KnowledgeSnapshot, UnitStats
from .base import validate_snapshot

MCP_URL = "https://metabot.gg/api/mcp"
# Nominal sample size for MetaBot aggregates (they process ~millions of games
# but don't expose per-comp N). Chosen so observed stats dominate the prior
# without being treated as exact.
AGGREGATE_PSEUDO_N = 1000

_PCT_RE = re.compile(r"([\d.]+)\s*%")
_UNIT_TOKEN_RE = re.compile(r"DA_\d+_|TFT\d+_|TFT_|DA_|_AD$|_AP$|\d+$")


def _post_mcp(method: str, params: dict[str, Any], timeout: float = 20.0) -> dict:
    body = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    ).encode()
    req = urllib.request.Request(
        MCP_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "tft-decision-engine",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = resp.read().decode("utf-8", errors="replace")
    # Streamable HTTP answers as SSE "data: {...}" lines.
    for line in payload.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            data = line[5:].strip()
            if data:
                return json.loads(data)
    return json.loads(payload)


def _percent(label_map: dict[str, str], key: str) -> float:
    raw = label_map.get(key, "")
    m = _PCT_RE.search(raw)
    return float(m.group(1)) / 100.0 if m else 0.0


def _avg_place(label_map: dict[str, str]) -> float:
    raw = label_map.get("Avg place", "")
    try:
        return float(raw)
    except ValueError:
        return 4.5


def _camel_to_words(token: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", token).strip()


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


class MetaBotAdapter:
    name = "metabot_gg"

    def __init__(
        self,
        patch: str,
        catalog_units: list[UnitStats] | None = None,
        timeout_s: float = 20.0,
    ) -> None:
        self.patch = patch
        self.timeout_s = timeout_s
        # apiName/name normalization table from the cdragon catalog.
        self._name_by_norm: dict[str, str] = {}
        for u in catalog_units or []:
            self._name_by_norm.setdefault(_normalize_name(u.name), u.name)

    def fetch(self) -> bytes:
        resp = _post_mcp(
            "tools/call",
            {
                "name": "get_team_comp",
                "arguments": {"game": "tft", "query": "best comps this patch"},
            },
            timeout=self.timeout_s,
        )
        return json.dumps(resp).encode()

    # -- normalization ------------------------------------------------------

    def _resolve_unit(self, api_token: str) -> str:
        token = _UNIT_TOKEN_RE.sub("", api_token)
        words = _camel_to_words(token)
        digitless = re.sub(r"\d+", "", words)  # e.g. KogMaw18 -> KogMaw
        for candidate in (
            words,
            digitless,
            digitless.split(" ")[0],
            token,
        ):
            hit = self._name_by_norm.get(_normalize_name(candidate))
            if hit:
                return hit
        return words or api_token

    def _units_from_url(self, url: str) -> frozenset[str]:
        # https://metabot.gg/en/TFT/comp/DA_18_X-DA_18_Y-.../overview
        slug = url.split("/comp/")[-1].split("/")[0]
        tokens = [t for t in slug.split("-") if t]
        return frozenset(self._resolve_unit(t) for t in tokens)

    def parse(self, raw: bytes) -> KnowledgeSnapshot:
        resp = json.loads(raw)
        content = (
            resp.get("result", {})
            .get("structuredContent", {})
        )
        entries = content.get("entries", [])
        if not entries:
            raise ValueError("metabot payload contains no comp entries")
        retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        patch = content.get("patch") or self.patch

        comps: list[CompStats] = []
        for entry in entries:
            stats = {s["label"]: s["value"] for s in entry.get("stats", [])}
            core = self._units_from_url(entry.get("url", ""))
            if not core:
                continue
            comps.append(
                CompStats(
                    name=entry.get("name", "unknown"),
                    composition_id=entry.get("url", "").split("/comp/")[-1].split("/")[0] or None,
                    average_placement=_avg_place(stats),
                    top4_rate=_percent(stats, "Top 4"),
                    win_rate=_percent(stats, "Win rate"),
                    play_rate=_percent(stats, "Pick rate"),
                    sample_size=AGGREGATE_PSEUDO_N,
                    core_units=core,
                    preferred_items=frozenset(),
                    rank_bucket=entry.get("tier"),
                    patch=self.patch,
                    source=self.name,
                    retrieved_at=retrieved_at,
                )
            )
        snapshot = KnowledgeSnapshot(
            patch=self.patch,
            source=self.name,
            retrieved_at=retrieved_at,
            comps=comps,
            units=None,  # stats source — does not own the catalog
            items=None,
            traits=None,
        )
        issues = validate_snapshot(snapshot)
        if issues:
            raise ValueError(f"metabot snapshot failed validation: {issues}")
        return snapshot
