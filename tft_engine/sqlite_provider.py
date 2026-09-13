"""SQLite-backed StatsProvider.

The knowledge cache is organized as immutable per-patch snapshots. Ingestion
inserts a full snapshot inside one transaction and flips `active` at the end,
so the live path either sees the whole previous snapshot or the whole new one.

Schema migrations are tracked with PRAGMA user_version.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from .stats import CompStats, ItemStats, KnowledgeSnapshot, TraitStats, UnitStats

def _locked(fn):
    """Serialize provider calls on the instance RLock (handler threads share
    one connection)."""

    def wrapper(self: "SQLiteStatsProvider", *args, **kwargs):
        with self._lock:
            return fn(self, *args, **kwargs)

    return wrapper


_SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY,
    patch TEXT NOT NULL,
    source TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    imported_at TEXT NOT NULL DEFAULT (datetime('now')),
    active INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS compositions (
    id INTEGER PRIMARY KEY,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    composition_id TEXT,
    rank_bucket TEXT,
    region TEXT,
    average_placement REAL NOT NULL,
    top4_rate REAL NOT NULL,
    win_rate REAL NOT NULL,
    play_rate REAL NOT NULL,
    sample_size INTEGER NOT NULL DEFAULT 0,
    typical_level INTEGER
);
CREATE INDEX IF NOT EXISTS idx_compositions_snapshot ON compositions(snapshot_id);

CREATE TABLE IF NOT EXISTS composition_units (
    composition_id INTEGER NOT NULL REFERENCES compositions(id) ON DELETE CASCADE,
    unit TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'core'  -- 'core' | 'optional'
);
CREATE INDEX IF NOT EXISTS idx_comp_units ON composition_units(composition_id);

CREATE TABLE IF NOT EXISTS composition_items (
    composition_id INTEGER NOT NULL REFERENCES compositions(id) ON DELETE CASCADE,
    item TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_comp_items ON composition_items(composition_id);

CREATE TABLE IF NOT EXISTS composition_augments (
    composition_id INTEGER NOT NULL REFERENCES compositions(id) ON DELETE CASCADE,
    augment TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS unit_stats (
    id INTEGER PRIMARY KEY,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    star_level INTEGER,
    stage TEXT,
    cost INTEGER,
    average_placement REAL NOT NULL,
    top4_rate REAL NOT NULL,
    win_rate REAL NOT NULL DEFAULT 0,
    play_rate REAL NOT NULL DEFAULT 0,
    sample_size INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_unit_stats ON unit_stats(snapshot_id, name);

CREATE TABLE IF NOT EXISTS unit_traits (
    unit_stats_id INTEGER NOT NULL REFERENCES unit_stats(id) ON DELETE CASCADE,
    trait TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS item_stats (
    id INTEGER PRIMARY KEY,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    holder TEXT,
    stage TEXT,
    composition TEXT,
    average_placement REAL NOT NULL,
    top4_rate REAL NOT NULL,
    win_rate REAL NOT NULL DEFAULT 0,
    play_rate REAL NOT NULL DEFAULT 0,
    sample_size INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_item_stats ON item_stats(snapshot_id, name);

CREATE TABLE IF NOT EXISTS trait_stats (
    id INTEGER PRIMARY KEY,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    breakpoint INTEGER,
    stage TEXT,
    average_placement REAL NOT NULL DEFAULT 4.5,
    top4_rate REAL NOT NULL DEFAULT 0,
    win_rate REAL NOT NULL DEFAULT 0,
    play_rate REAL NOT NULL DEFAULT 0,
    sample_size INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_trait_stats ON trait_stats(snapshot_id, name);

CREATE INDEX IF NOT EXISTS idx_snapshots_patch ON snapshots(patch, active);
"""


class SQLiteStatsProvider:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if self.path.parent and str(self.path.parent) not in ("", "."):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        # The provider is shared across HTTP handler threads; serialize access.
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "SQLiteStatsProvider":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ---- schema management -------------------------------------------------

    def _migrate(self) -> None:
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        if version < 1:
            self.conn.executescript(_SCHEMA)
            self.conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
            self.conn.commit()
        elif version > _SCHEMA_VERSION:
            raise RuntimeError(
                f"database schema v{version} is newer than supported v{_SCHEMA_VERSION}"
            )

    # ---- ingestion ---------------------------------------------------------

    @_locked
    def apply_snapshot(self, snapshot: KnowledgeSnapshot) -> int:
        """Insert a complete snapshot and atomically make it the active one for
        its patch. Sections left as None on the snapshot inherit the previous
        active snapshot's rows for that patch, so sources can refresh only the
        data they own. Returns the new snapshot id."""
        with self.conn:  # single transaction: all-or-nothing
            prev = self._active_snapshot_id(snapshot.patch)
            cur = self.conn.execute(
                "INSERT INTO snapshots (patch, source, retrieved_at, active)"
                " VALUES (?, ?, ?, 0)",
                (snapshot.patch, snapshot.source, snapshot.retrieved_at),
            )
            sid = int(cur.lastrowid)

            if snapshot.comps is None:
                if prev is not None:
                    self._copy_comp_section(prev, sid)
            else:
                self._insert_comps(sid, snapshot.comps)

            if snapshot.units is None:
                if prev is not None:
                    self._copy_unit_section(prev, sid)
            else:
                self._insert_units(sid, snapshot.units)

            if snapshot.items is None:
                if prev is not None:
                    self.conn.execute(
                        """INSERT INTO item_stats
                           (snapshot_id, name, holder, stage, composition,
                            average_placement, top4_rate, win_rate, play_rate,
                            sample_size)
                           SELECT ?, name, holder, stage, composition,
                                  average_placement, top4_rate, win_rate,
                                  play_rate, sample_size
                           FROM item_stats WHERE snapshot_id = ?""",
                        (sid, prev),
                    )
            else:
                for item in snapshot.items:
                    self.conn.execute(
                        """INSERT INTO item_stats
                           (snapshot_id, name, holder, stage, composition,
                            average_placement, top4_rate, win_rate, play_rate, sample_size)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            sid, item.name, item.holder, item.stage, item.composition,
                            item.average_placement, item.top4_rate, item.win_rate,
                            item.play_rate, item.sample_size,
                        ),
                    )

            if snapshot.traits is None:
                if prev is not None:
                    self.conn.execute(
                        """INSERT INTO trait_stats
                           (snapshot_id, name, breakpoint, stage, average_placement,
                            top4_rate, win_rate, play_rate, sample_size)
                           SELECT ?, name, breakpoint, stage, average_placement,
                                  top4_rate, win_rate, play_rate, sample_size
                           FROM trait_stats WHERE snapshot_id = ?""",
                        (sid, prev),
                    )
            else:
                for trait in snapshot.traits:
                    self.conn.execute(
                        """INSERT INTO trait_stats
                           (snapshot_id, name, breakpoint, stage, average_placement,
                            top4_rate, win_rate, play_rate, sample_size)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            sid, trait.name, trait.breakpoint, trait.stage,
                            trait.average_placement, trait.top4_rate, trait.win_rate,
                            trait.play_rate, trait.sample_size,
                        ),
                    )

            # Atomic swap: deactivate previous snapshots for this patch.
            self.conn.execute(
                "UPDATE snapshots SET active = 0 WHERE patch = ? AND id != ?",
                (snapshot.patch, sid),
            )
            self.conn.execute("UPDATE snapshots SET active = 1 WHERE id = ?", (sid,))
        return sid

    def _insert_comps(self, sid: int, comps: list[CompStats]) -> None:
        for comp in comps:
            cur = self.conn.execute(
                """INSERT INTO compositions
                   (snapshot_id, name, composition_id, rank_bucket, region,
                    average_placement, top4_rate, win_rate, play_rate,
                    sample_size, typical_level)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    sid, comp.name, comp.composition_id, comp.rank_bucket,
                    comp.region, comp.average_placement, comp.top4_rate,
                    comp.win_rate, comp.play_rate, comp.sample_size,
                    comp.typical_level,
                ),
            )
            comp_row = int(cur.lastrowid)
            self.conn.executemany(
                "INSERT INTO composition_units (composition_id, unit, role)"
                " VALUES (?, ?, ?)",
                [(comp_row, u, "core") for u in sorted(comp.core_units)]
                + [(comp_row, u, "optional") for u in sorted(comp.optional_units)],
            )
            self.conn.executemany(
                "INSERT INTO composition_items (composition_id, item) VALUES (?, ?)",
                [(comp_row, i) for i in sorted(comp.preferred_items)],
            )
            self.conn.executemany(
                "INSERT INTO composition_augments (composition_id, augment)"
                " VALUES (?, ?)",
                [(comp_row, a) for a in sorted(comp.augment_preferences)],
            )

    def _copy_comp_section(self, prev_sid: int, sid: int) -> None:
        rows = self.conn.execute(
            "SELECT * FROM compositions WHERE snapshot_id = ?", (prev_sid,)
        ).fetchall()
        for r in rows:
            cur = self.conn.execute(
                """INSERT INTO compositions
                   (snapshot_id, name, composition_id, rank_bucket, region,
                    average_placement, top4_rate, win_rate, play_rate,
                    sample_size, typical_level)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    sid, r["name"], r["composition_id"], r["rank_bucket"],
                    r["region"], r["average_placement"], r["top4_rate"],
                    r["win_rate"], r["play_rate"], r["sample_size"],
                    r["typical_level"],
                ),
            )
            new_id = int(cur.lastrowid)
            for table, col in (
                ("composition_units", "unit"),
                ("composition_items", "item"),
                ("composition_augments", "augment"),
            ):
                extra = ", role" if table == "composition_units" else ""
                extra_sel = ", role" if table == "composition_units" else ""
                self.conn.execute(
                    f"""INSERT INTO {table} (composition_id, {col}{extra})
                        SELECT ?, {col}{extra_sel} FROM {table}
                        WHERE composition_id = ?""",
                    (new_id, r["id"]),
                )

    def _insert_units(self, sid: int, units: list[UnitStats]) -> None:
        for unit in units:
            cur = self.conn.execute(
                """INSERT INTO unit_stats
                   (snapshot_id, name, star_level, stage, cost,
                    average_placement, top4_rate, win_rate, play_rate, sample_size)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    sid, unit.name, unit.star_level, unit.stage, unit.cost,
                    unit.average_placement, unit.top4_rate, unit.win_rate,
                    unit.play_rate, unit.sample_size,
                ),
            )
            unit_row = int(cur.lastrowid)
            self.conn.executemany(
                "INSERT INTO unit_traits (unit_stats_id, trait) VALUES (?, ?)",
                [(unit_row, t) for t in sorted(unit.traits)],
            )

    def _copy_unit_section(self, prev_sid: int, sid: int) -> None:
        rows = self.conn.execute(
            "SELECT * FROM unit_stats WHERE snapshot_id = ?", (prev_sid,)
        ).fetchall()
        for r in rows:
            cur = self.conn.execute(
                """INSERT INTO unit_stats
                   (snapshot_id, name, star_level, stage, cost,
                    average_placement, top4_rate, win_rate, play_rate, sample_size)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    sid, r["name"], r["star_level"], r["stage"], r["cost"],
                    r["average_placement"], r["top4_rate"], r["win_rate"],
                    r["play_rate"], r["sample_size"],
                ),
            )
            self.conn.execute(
                """INSERT INTO unit_traits (unit_stats_id, trait)
                   SELECT ?, trait FROM unit_traits WHERE unit_stats_id = ?""",
                (int(cur.lastrowid), r["id"]),
            )

    # ---- queries (live path) ----------------------------------------------

    def _active_snapshot_id(self, patch: str) -> int | None:
        row = self.conn.execute(
            "SELECT id FROM snapshots WHERE patch = ? AND active = 1"
            " ORDER BY id DESC LIMIT 1",
            (patch,),
        ).fetchone()
        return int(row["id"]) if row else None

    @_locked
    def get_comps(self, patch: str) -> list[CompStats]:
        sid = self._active_snapshot_id(patch)
        if sid is None:
            return []
        rows = self.conn.execute(
            "SELECT * FROM compositions WHERE snapshot_id = ?", (sid,)
        ).fetchall()
        units: dict[int, dict[str, set[str]]] = {}
        for r in self.conn.execute(
            """SELECT cu.composition_id, cu.unit, cu.role
               FROM composition_units cu
               JOIN compositions c ON c.id = cu.composition_id
               WHERE c.snapshot_id = ?""",
            (sid,),
        ):
            units.setdefault(r["composition_id"], {"core": set(), "optional": set()})[
                r["role"]
            ].add(r["unit"])
        items: dict[int, set[str]] = {}
        for r in self.conn.execute(
            """SELECT ci.composition_id, ci.item
               FROM composition_items ci
               JOIN compositions c ON c.id = ci.composition_id
               WHERE c.snapshot_id = ?""",
            (sid,),
        ):
            items.setdefault(r["composition_id"], set()).add(r["item"])
        augs: dict[int, set[str]] = {}
        for r in self.conn.execute(
            """SELECT ca.composition_id, ca.augment
               FROM composition_augments ca
               JOIN compositions c ON c.id = ca.composition_id
               WHERE c.snapshot_id = ?""",
            (sid,),
        ):
            augs.setdefault(r["composition_id"], set()).add(r["augment"])
        snap = self.conn.execute(
            "SELECT source, retrieved_at FROM snapshots WHERE id = ?", (sid,)
        ).fetchone()
        return [
            CompStats(
                name=r["name"],
                average_placement=r["average_placement"],
                top4_rate=r["top4_rate"],
                win_rate=r["win_rate"],
                play_rate=r["play_rate"],
                core_units=frozenset(units.get(r["id"], {}).get("core", set())),
                optional_units=frozenset(units.get(r["id"], {}).get("optional", set())),
                preferred_items=frozenset(items.get(r["id"], set())),
                augment_preferences=frozenset(augs.get(r["id"], set())),
                patch=patch,
                composition_id=r["composition_id"],
                rank_bucket=r["rank_bucket"],
                region=r["region"],
                sample_size=r["sample_size"],
                typical_level=r["typical_level"],
                source=snap["source"],
                retrieved_at=snap["retrieved_at"],
            )
            for r in rows
        ]

    @_locked
    def get_unit(self, patch: str, name: str) -> UnitStats | None:
        sid = self._active_snapshot_id(patch)
        if sid is None:
            return None
        rows = self.conn.execute(
            "SELECT * FROM unit_stats WHERE snapshot_id = ? AND name = ?"
            " ORDER BY sample_size DESC",
            (sid, name),
        ).fetchall()
        if not rows:
            return None
        # Prefer the aggregated record (no star/stage conditioning).
        row = next(
            (r for r in rows if r["star_level"] is None and r["stage"] is None),
            rows[0],
        )
        traits = {
            r["trait"]
            for r in self.conn.execute(
                "SELECT trait FROM unit_traits WHERE unit_stats_id = ?", (row["id"],)
            )
        }
        return UnitStats(
            name=row["name"],
            average_placement=row["average_placement"],
            top4_rate=row["top4_rate"],
            win_rate=row["win_rate"],
            play_rate=row["play_rate"],
            star_level=row["star_level"],
            stage=row["stage"],
            cost=row["cost"],
            traits=frozenset(traits),
            sample_size=row["sample_size"],
            patch=patch,
        )

    @_locked
    def get_units(self, patch: str) -> list[UnitStats]:
        """All unit records in the active snapshot (prefers aggregated rows)."""
        sid = self._active_snapshot_id(patch)
        if sid is None:
            return []
        rows = self.conn.execute(
            "SELECT * FROM unit_stats WHERE snapshot_id = ?", (sid,)
        ).fetchall()
        trait_rows = self.conn.execute(
            """SELECT ut.unit_stats_id, ut.trait FROM unit_traits ut
               JOIN unit_stats u ON u.id = ut.unit_stats_id
               WHERE u.snapshot_id = ?""",
            (sid,),
        ).fetchall()
        traits_by_row: dict[int, set[str]] = {}
        for r in trait_rows:
            traits_by_row.setdefault(r["unit_stats_id"], set()).add(r["trait"])
        return [
            UnitStats(
                name=r["name"],
                average_placement=r["average_placement"],
                top4_rate=r["top4_rate"],
                win_rate=r["win_rate"],
                play_rate=r["play_rate"],
                star_level=r["star_level"],
                stage=r["stage"],
                cost=r["cost"],
                traits=frozenset(traits_by_row.get(r["id"], set())),
                sample_size=r["sample_size"],
                patch=patch,
            )
            for r in rows
        ]

    @_locked
    def get_item(self, patch: str, name: str) -> ItemStats | None:
        sid = self._active_snapshot_id(patch)
        if sid is None:
            return None
        rows = self.conn.execute(
            "SELECT * FROM item_stats WHERE snapshot_id = ? AND name = ?"
            " ORDER BY sample_size DESC",
            (sid, name),
        ).fetchall()
        if not rows:
            return None
        row = next(
            (
                r
                for r in rows
                if r["holder"] is None and r["stage"] is None and r["composition"] is None
            ),
            rows[0],
        )
        return ItemStats(
            name=row["name"],
            average_placement=row["average_placement"],
            top4_rate=row["top4_rate"],
            win_rate=row["win_rate"],
            play_rate=row["play_rate"],
            holder=row["holder"],
            stage=row["stage"],
            composition=row["composition"],
            sample_size=row["sample_size"],
            patch=patch,
        )

    @_locked
    def get_traits(self, patch: str) -> list[TraitStats]:
        sid = self._active_snapshot_id(patch)
        if sid is None:
            return []
        return [
            TraitStats(
                name=r["name"],
                breakpoint=r["breakpoint"],
                stage=r["stage"],
                average_placement=r["average_placement"],
                top4_rate=r["top4_rate"],
                win_rate=r["win_rate"],
                play_rate=r["play_rate"],
                sample_size=r["sample_size"],
                patch=patch,
            )
            for r in self.conn.execute(
                "SELECT * FROM trait_stats WHERE snapshot_id = ?", (sid,)
            )
        ]

    @_locked
    def knowledge_status(self) -> dict[str, object]:
        snaps = [
            {
                "id": r["id"],
                "patch": r["patch"],
                "source": r["source"],
                "retrieved_at": r["retrieved_at"],
                "imported_at": r["imported_at"],
                "active": bool(r["active"]),
                "compositions": r["comps"],
                "unit_stats": r["units"],
                "item_stats": r["items"],
                "trait_stats": r["traits"],
            }
            for r in self.conn.execute(
                """SELECT s.id, s.patch, s.source, s.retrieved_at, s.imported_at,
                          s.active,
                          (SELECT COUNT(*) FROM compositions c WHERE c.snapshot_id = s.id) AS comps,
                          (SELECT COUNT(*) FROM unit_stats u WHERE u.snapshot_id = s.id) AS units,
                          (SELECT COUNT(*) FROM item_stats i WHERE i.snapshot_id = s.id) AS items,
                          (SELECT COUNT(*) FROM trait_stats t WHERE t.snapshot_id = s.id) AS traits
                   FROM snapshots s ORDER BY s.id DESC"""
            )
        ]
        return {
            "db_path": str(self.path),
            "schema_version": _SCHEMA_VERSION,
            "snapshots": snaps,
        }
