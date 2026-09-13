"""CLI: python -m tft_engine.ingest --source cdragon --patch 18.1 --db data/tft.db"""

from __future__ import annotations

import argparse
import json
import sys

from ..sqlite_provider import SQLiteStatsProvider
from .cdragon import CommunityDragonAdapter
from .pipeline import run_ingestion


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tft_engine.ingest")
    ap.add_argument("--source", choices=["cdragon"], required=True)
    ap.add_argument("--patch", required=True, help="patch label, e.g. 18.1")
    ap.add_argument("--set", dest="set_number", type=int, default=None,
                    help="TFT set number; defaults to latest in payload")
    ap.add_argument("--db", default="data/tft.db")
    ap.add_argument("--version", default="latest", help="cdragon version path")
    args = ap.parse_args(argv)

    if args.source == "cdragon":
        adapter = CommunityDragonAdapter(
            patch=args.patch, set_number=args.set_number, version=args.version
        )
    else:  # pragma: no cover
        ap.error(f"unknown source {args.source}")

    with SQLiteStatsProvider(args.db) as provider:
        result = run_ingestion(adapter, provider)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
