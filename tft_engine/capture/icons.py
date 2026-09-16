"""Download and cache champion square portraits for template matching.

Source: Community Dragon's `squareIcon` asset per champion — the same splash
crop the in-game shop card renders, which sunderarmor's face icons are not.
Cached under `data/icons/{set}/`; the live path never fetches.
"""

from __future__ import annotations

import json
import re
import ssl
import urllib.request
from pathlib import Path

CDRAGON_JSON = "https://raw.communitydragon.org/latest/cdragon/tft/en_us.json"
CDRAGON_ASSET = "https://raw.communitydragon.org/latest/game/{path}"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TFTDecisionEngine"}


def _ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return ctx


def icon_filename(unit_name: str) -> str:
    """Canonical local name: 'Kog'Maw' -> 'Kogmaw.png'."""
    base = re.sub(r"[^a-z0-9]", "", unit_name.lower())
    return base.capitalize() + ".png"


def champion_icon_urls(set_number: int) -> dict[str, str]:
    """{display name: squareIcon URL} for every champion in the set."""
    req = urllib.request.Request(CDRAGON_JSON, headers=UA)
    with urllib.request.urlopen(req, timeout=30, context=_ctx()) as resp:
        data = json.loads(resp.read())
    sets = data["sets"]
    key = str(set_number) if str(set_number) in sets else sorted(sets, key=int)[-1]
    urls: dict[str, str] = {}
    for champ in sets[key]["champions"]:
        path = champ.get("squareIcon") or champ.get("icon") or ""
        name = champ.get("name")
        if name and path:
            urls[name] = CDRAGON_ASSET.format(
                path=re.sub(r"\.tex$", ".png", path, flags=re.I)
            )
    return urls


def ensure_icons(
    unit_names: list[str], set_no: int, out_dir: Path
) -> dict[str, Path]:
    """Download missing square portraits; returns {unit_name: path}."""
    out_dir.mkdir(parents=True, exist_ok=True)
    urls = champion_icon_urls(set_no)
    result: dict[str, Path] = {}
    for name in unit_names:
        path = out_dir / icon_filename(name)
        if not path.exists() and name in urls:
            req = urllib.request.Request(urls[name], headers=UA)
            try:
                with urllib.request.urlopen(req, timeout=20, context=_ctx()) as resp:
                    path.write_bytes(resp.read())
            except Exception:
                continue
        if path.exists():
            result[name] = path
    return result
