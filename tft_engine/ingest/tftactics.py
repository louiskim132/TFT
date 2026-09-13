"""TFTactics.gg adapter — server-rendered tier list with per-unit items and
tempo tags.

The team-comps page is plain HTML (no JS gate): each `team-portrait` card
carries a rank (S/A/B/C), a comp name, a playstyle tag ("Slow Roll (5)",
"Fast 8", "Standard", "Augment", "Emblem"), the unit roster, and recommended
items per unit. This source carries NO performance statistics — it provides
structure (roster, item priorities, level plan). Stats come from MetaBot.
"""

from __future__ import annotations

import re
import ssl
import urllib.request
from datetime import datetime, timezone

from ..stats import CompStats, KnowledgeSnapshot
from .base import validate_snapshot

TEAM_COMPS_URL = "https://tftactics.gg/tierlist/team-comps/"

_CARD_RE = re.compile(r'<div class="team-portrait">', re.S)
_RANK_RE = re.compile(r'team-rank\s+tone">(\w)<', re.S)
_NAME_RE = re.compile(r'team-name-elipsis">([^<]+)<', re.S)
_STYLE_RE = re.compile(r'team-playstyle">([^<]+)<', re.S)
_UNIT_RE = re.compile(r'<a href="/champions/[^"]*"[^>]*>(.*?)</a>', re.S)
_UNIT_NAME_RE = re.compile(r'team-character-name">([^<]+)<')
_ITEM_RE = re.compile(r'character-wrapper"\s+name="([^"]+)"')
_LEVEL_RE = re.compile(r"\((\d+)\)")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TFTDecisionEngine"}


def _style_to_level(style: str) -> int | None:
    """'Slow Roll (5)' -> 5; 'Fast 8'/'Fast 9' -> 8/9; else None."""
    m = _LEVEL_RE.search(style)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)", style)
    return int(m.group(1)) if m else None


class TFTacticsAdapter:
    name = "tftactics"

    def __init__(self, patch: str, timeout_s: float = 20.0) -> None:
        self.patch = patch
        self.timeout_s = timeout_s
        self.url = TEAM_COMPS_URL

    def fetch(self) -> bytes:
        # Netlify serves a Let's Encrypt "Root YE" cross-signed chain that
        # OpenSSL's strict mode rejects; non-strict still verifies signatures.
        ctx = ssl.create_default_context()
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
        req = urllib.request.Request(self.url, headers=UA)
        with urllib.request.urlopen(req, timeout=self.timeout_s, context=ctx) as resp:
            return resp.read()

    def parse(self, raw: bytes) -> KnowledgeSnapshot:
        html = raw.decode("utf-8", errors="replace")
        cards = _CARD_RE.split(html)[1:]
        if not cards:
            raise ValueError("tftactics payload contains no comp cards")
        retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

        comps: list[CompStats] = []
        for card in cards:
            rank = _RANK_RE.search(card)
            name = _NAME_RE.search(card)
            style = _STYLE_RE.search(card)
            if not (rank and name):
                continue
            units: set[str] = set()
            items: set[str] = set()
            for unit_html in _UNIT_RE.findall(card):
                unit_name = _UNIT_NAME_RE.search(unit_html)
                if unit_name:
                    units.add(unit_name.group(1).strip())
                items.update(_ITEM_RE.findall(unit_html))
            if not units:
                continue
            comps.append(
                CompStats(
                    name=name.group(1).strip(),
                    average_placement=4.5,  # neutral; stats come from MetaBot
                    top4_rate=0.0,
                    win_rate=0.0,
                    play_rate=0.0,
                    sample_size=0,
                    core_units=frozenset(units),
                    preferred_items=frozenset(items),
                    rank_bucket=rank.group(1),
                    typical_level=_style_to_level(style.group(1)) if style else None,
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
            units=None,
            items=None,
            traits=None,
        )
        issues = validate_snapshot(snapshot)
        if issues:
            raise ValueError(f"tftactics snapshot failed validation: {issues}")
        return snapshot
