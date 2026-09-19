#!/usr/bin/env python
"""Full-catalog OpenRouter picker for Hermes Agent (and any curated-catalog client).

THE PROBLEM
-----------
Hermes' OpenRouter picker intersects a small CURATED model list with the live
OpenRouter catalog. The curated list (~59 ids, shipped in-repo + remote manifest)
is the bottleneck: OpenRouter serves ~450 models, ~380 of which are text-output,
tool-calling capable — but the picker only ever shows the curated handful that
survive the live `tools` filter (~34-49 today). The missing models are not
broken; they're simply not on anyone's curation list.

THE FIX (no source edits — survives `hermes update`)
---------------------------------------------------
Hermes supports per-provider catalog override URLs:

    model_catalog:
      providers:
        openrouter:
          url: <your own manifest>

`_get_provider_block()` fetches that URL INSTEAD of the master manifest for the
openrouter block only (Nous Portal etc. still resolve normally). This script
generates that manifest from the LIVE OpenRouter catalog:

  * every text-output model that advertises `tools` (the hard requirement for
    an agent), curated flagships first so the good models lead the picker,
  * then everything else newest-first, so day-one models appear automatically,
  * badges ("recommended") are applied by Hermes itself to the top entry.

Hermes still intersects the result with the live catalog and drops anything
that does not advertise `tools` — so this manifest only needs to be a superset.
Stale/retired ids self-clean on every refresh.

INSTALL (3 steps, any OS)
-------------------------
  1. Save this file to ~/.hermes/scripts/refresh_openrouter_catalog.py
  2. python ~/.hermes/scripts/refresh_openrouter_catalog.py
     (prints the exact `hermes config set` command for your OS)
  3. Run that command, restart Hermes, open /model — full catalog.

OPTIONAL: schedule it (new OpenRouter models then appear on their own), e.g.
Hermes cron: 12h interval, no_agent, script=refresh_openrouter_catalog.py
or any OS scheduler. Offline runs leave the existing manifest untouched.

Works on Windows / macOS / Linux. Python 3.9+, stdlib only.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERMES_AGENT = Path.home() / ".hermes" / "hermes-agent"
OUT_PATH = Path.home() / ".hermes" / "catalog" / "openrouter-full.json"


def supports_tools(item: dict) -> bool:
    """Mirror of hermes_cli.models._openrouter_model_supports_tools (permissive when absent)."""
    params = item.get("supported_parameters")
    return ("tools" in params) if isinstance(params, list) else True


def outputs_text(item: dict) -> bool:
    """True for chat/completion models; excludes image/video/audio-only endpoints."""
    arch = item.get("architecture") or {}
    outs = arch.get("output_modalities")
    if isinstance(outs, list):
        return "text" in outs
    return str(arch.get("modality", "")).endswith("->text")


def file_url(path: Path) -> str:
    """file:// URL that urllib on the user's platform will resolve."""
    p = path.resolve()
    return p.as_uri() if hasattr(p, "as_uri") else f"file://{p}"


def main() -> int:
    sys.path.insert(0, str(HERMES_AGENT))
    try:
        from hermes_cli.models import (
            _OPENROUTER_CATALOG_URL,
            _fetch_live_catalog_index,
            _urlopen_model_catalog_request,
        )
        from hermes_cli.models_catalog_static import OPENROUTER_MODELS
    except Exception as exc:
        print(f"error: could not import hermes_cli from {HERMES_AGENT} ({exc})", file=sys.stderr)
        print("install Hermes Agent first, or adjust HERMES_AGENT at the top of this file.", file=sys.stderr)
        return 2

    fetched = _fetch_live_catalog_index(str(_OPENROUTER_CATALOG_URL), 20.0, _urlopen_model_catalog_request)
    if fetched is None:
        print("openrouter catalog unreachable; leaving existing manifest untouched", file=sys.stderr)
        return 1
    items, by_id = fetched

    usable = lambda m: supports_tools(m) and outputs_text(m)  # noqa: E731

    # Curated names lead the list, in curated order. Curated ids that are retired or
    # tool-less live (fast/flex tiers, pareto-code, some :free SKUs) are dropped rather
    # than shipped, since Hermes would filter them out anyway.
    curated_ids = [mid for mid, _ in OPENROUTER_MODELS]
    head = [mid for mid in curated_ids if mid in by_id and usable(by_id[mid])]
    head_set = set(head)

    # Then everything else tool-capable, newest first.
    rest = sorted(
        (mid for mid, m in by_id.items() if mid not in head_set and usable(m)),
        key=lambda mid: by_id[mid].get("created") or 0,
        reverse=True,
    )
    order = head + rest
    dropped = [mid for mid in curated_ids if mid not in head_set]

    manifest = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metadata": {
            "source": "full-catalog picker override (refresh_openrouter_catalog.py)",
            "note": (
                "Curated flagships first, then every text-output tool-capable OpenRouter model "
                "from the live catalog, newest first."
            ),
        },
        "providers": {
            "openrouter": {
                "metadata": {"display_name": "OpenRouter (full live catalog)"},
                "models": [{"id": mid} for mid in order],
            }
        },
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write: the picker may read this concurrently.
    fd, tmp = tempfile.mkstemp(dir=str(OUT_PATH.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=1)
        os.replace(tmp, OUT_PATH)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise

    print(f"wrote {OUT_PATH}")
    print(f"  live catalog:       {len(items)} models")
    print(f"  tool-capable text:  {len(order)} models  (was ~34 in the stock picker)")
    print(f"  curated leading:    {len(head)}")
    if dropped:
        print(f"  curated dropped (retired or no tool support): {len(dropped)}")

    url = file_url(OUT_PATH)
    print()
    print("If you have not already, wire the picker to this manifest:")
    print(f'  hermes config set model_catalog.providers.openrouter.url "{url}"')
    print("then restart Hermes and open /model.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())