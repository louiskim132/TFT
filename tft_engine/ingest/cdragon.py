"""Community Dragon adapter.

Fetches the TFT set catalog (champions with cost/traits, traits with
breakpoints, completed items with recipes) from raw.communitydragon.org.
This is a *catalog* source — it carries no performance statistics, so the
snapshot it emits populates unit/trait/item records with sample_size=0 and
leaves the comps section untouched (None) for a stats adapter to own.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone

from ..stats import ItemStats, KnowledgeSnapshot, TraitStats, UnitStats
from .base import validate_snapshot

CDRAGON_URL = "https://raw.communitydragon.org/{version}/cdragon/tft/en_us.json"


class CommunityDragonAdapter:
    name = "community_dragon"

    def __init__(
        self,
        patch: str,
        set_number: int | None = None,
        version: str = "latest",
        timeout_s: float = 30.0,
    ) -> None:
        self.patch = patch
        self.set_number = set_number
        self.url = CDRAGON_URL.format(version=version)
        self.timeout_s = timeout_s

    def fetch(self) -> bytes:
        req = urllib.request.Request(self.url, headers={"User-Agent": "tft-decision-engine"})
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            return resp.read()

    def parse(self, raw: bytes) -> KnowledgeSnapshot:
        data = json.loads(raw)
        sets = data.get("sets")
        if not isinstance(sets, dict) or not sets:
            raise ValueError("cdragon payload missing 'sets'")
        set_key = str(self.set_number) if self.set_number else max(sets, key=int)
        set_data = sets.get(set_key)
        if set_data is None:
            raise ValueError(f"set {set_key} not present; available: {sorted(sets, key=int)}")
        retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

        trait_name_by_api = {
            t["apiName"]: t["name"] for t in set_data.get("traits", [])
        }
        units = [
            UnitStats(
                name=c["name"],
                cost=int(c.get("cost", 0)),
                traits=frozenset(
                    trait_name_by_api.get(t, t) for t in c.get("traits", [])
                ),
                patch=self.patch,
                source=self.name,
                retrieved_at=retrieved_at,
            )
            for c in set_data.get("champions", [])
            if c.get("name") and int(c.get("cost", 0)) >= 1
        ]

        traits: list[TraitStats] = []
        for t in set_data.get("traits", []):
            name = t.get("name")
            if not name:
                continue
            for effect in t.get("effects", []) or []:
                bp = effect.get("minUnits")
                if bp:
                    traits.append(
                        TraitStats(
                            name=name,
                            breakpoint=int(bp),
                            patch=self.patch,
                            source=self.name,
                            retrieved_at=retrieved_at,
                        )
                    )

        items = [
            ItemStats(
                name=i["name"],
                average_placement=0.0,
                top4_rate=0.0,
                patch=self.patch,
                source=self.name,
                retrieved_at=retrieved_at,
            )
            for i in data.get("items", [])
            if i.get("name") and i.get("composition") and not i.get("isAugment")
        ]

        snapshot = KnowledgeSnapshot(
            patch=self.patch,
            source=self.name,
            retrieved_at=retrieved_at,
            comps=None,  # catalog source — does not own comp stats
            units=units,
            items=items,
            traits=traits,
        )
        issues = validate_snapshot(snapshot)
        if issues:
            raise ValueError(f"cdragon snapshot failed validation: {issues}")
        return snapshot
