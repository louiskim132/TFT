"""Source adapter contract.

An adapter fetches raw bytes from one upstream source and normalizes them into
a KnowledgeSnapshot. Network access lives here and ONLY here — the decision
engine never touches it.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..stats import KnowledgeSnapshot


@runtime_checkable
class SourceAdapter(Protocol):
    name: str

    def fetch(self) -> bytes:
        """Retrieve raw payload from the source."""
        ...

    def parse(self, raw: bytes) -> KnowledgeSnapshot:
        """Normalize raw payload into a snapshot. Raises ValueError on
        unparseable payloads — never returns a partial snapshot."""
        ...


def validate_snapshot(snapshot: KnowledgeSnapshot) -> list[str]:
    """Quality gates run before a snapshot may be swapped in. Returns a list of
    issues; empty means the snapshot is safe to apply."""
    issues: list[str] = []
    if not snapshot.patch:
        issues.append("snapshot has no patch label")
    if not snapshot.source:
        issues.append("snapshot has no source label")
    if not snapshot.retrieved_at:
        issues.append("snapshot has no retrieved_at")

    if snapshot.units is not None:
        if len(snapshot.units) == 0:
            issues.append("units section explicitly empty")
        for u in snapshot.units:
            if not u.name:
                issues.append("unit record missing name")
            if u.cost is not None and not 0 <= u.cost <= 15:
                issues.append(f"unit {u.name} implausible cost {u.cost}")
    if snapshot.traits is not None:
        for t in snapshot.traits:
            if not t.name:
                issues.append("trait record missing name")
            if t.breakpoint is not None and not 0 < t.breakpoint <= 12:
                issues.append(f"trait {t.name} implausible breakpoint {t.breakpoint}")
    if snapshot.comps is not None:
        for c in snapshot.comps:
            if not c.name:
                issues.append("comp record missing name")
            if not 1.0 <= c.average_placement <= 8.0:
                issues.append(f"comp {c.name} avg placement {c.average_placement} out of range")
            if not 0.0 <= c.top4_rate <= 1.0 or not 0.0 <= c.win_rate <= 1.0:
                issues.append(f"comp {c.name} rates out of [0,1]")
    if snapshot.items is not None:
        for i in snapshot.items:
            if not i.name:
                issues.append("item record missing name")
    return issues
