"""CLI: python -m tft_engine.ingest --source cdragon --patch 18.1 --db data/tft.db"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from ..sqlite_provider import SQLiteStatsProvider
from ..stats import KnowledgeSnapshot
from .cdragon import CommunityDragonAdapter
from .metabot import MetaBotAdapter
from .pipeline import merge_comp_sources, run_ingestion
from .tftactics import TFTacticsAdapter


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tft_engine.ingest")
    ap.add_argument(
        "--source",
        choices=["cdragon", "metabot", "tftactics", "full"],
        required=True,
    )
    ap.add_argument("--patch", required=True, help="patch label, e.g. 18.1")
    ap.add_argument("--set", dest="set_number", type=int, default=None,
                    help="TFT set number; defaults to latest in payload")
    ap.add_argument("--db", default="data/tft.db")
    ap.add_argument("--version", default="latest", help="cdragon version path")
    args = ap.parse_args(argv)

    with SQLiteStatsProvider(args.db) as provider:
        if args.source == "cdragon":
            adapter = CommunityDragonAdapter(
                patch=args.patch, set_number=args.set_number, version=args.version
            )
            results = [run_ingestion(adapter, provider)]
        elif args.source == "metabot":
            catalog = provider.get_units(args.patch)
            adapter = MetaBotAdapter(patch=args.patch, catalog_units=catalog)
            results = [run_ingestion(adapter, provider)]
        elif args.source == "tftactics":
            results = [run_ingestion(TFTacticsAdapter(patch=args.patch), provider)]
        else:  # full: catalog first, then merged stats + structure on top
            results = [
                run_ingestion(
                    CommunityDragonAdapter(
                        patch=args.patch,
                        set_number=args.set_number,
                        version=args.version,
                    ),
                    provider,
                )
            ]
            catalog = provider.get_units(args.patch)
            mb_adapter = MetaBotAdapter(patch=args.patch, catalog_units=catalog)
            tft_adapter = TFTacticsAdapter(patch=args.patch)
            merged_comps = merge_comp_sources(
                mb_adapter.parse(mb_adapter.fetch()).comps or [],
                tft_adapter.parse(tft_adapter.fetch()).comps or [],
            )
            merged = KnowledgeSnapshot(
                patch=args.patch,
                source="metabot_gg+tftactics",
                retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                comps=merged_comps,
            )
            snapshot_id = provider.apply_snapshot(merged)
            results.append(
                {
                    "snapshot_id": snapshot_id,
                    "patch": merged.patch,
                    "source": merged.source,
                    "retrieved_at": merged.retrieved_at,
                    "counts": {"comps": len(merged.comps or [])},
                }
            )
    print(json.dumps(results[0] if len(results) == 1 else results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
