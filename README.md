# hermes-openrouter-full-picker

![OpenRouter × Hermes — Leveling Up](banner.png)

Hermes Agent's `/model` picker shows ~34 of OpenRouter's ~450 models. This script makes
it show **all ~380 text-output, tool-calling-capable ones** (verified live: **376 of 445**
on 2026-09-21) — no source edits, survives
`hermes update`, zero cost. Curated flagships stay on top; brand-new models appear on
their own day one (xiaomi mimo-v2.6 hit the picker the same day it dropped on OpenRouter).

## Why the stock picker is tiny

Hermes never lists the full OpenRouter catalog. It intersects a small **curated list**
(~59 ids, shipped in-repo and in a remote manifest) with the live catalog, then drops
anything that doesn't advertise `tools` in `supported_parameters` (agents need tool
calls). ~34-49 models survive. The other ~330+ aren't broken — they're simply not on
anyone's curation list.

## The fix

Hermes supports per-provider catalog override URLs:

```yaml
model_catalog:
  providers:
    openrouter:
      url: <your own manifest>
```

`_get_provider_block()` (hermes_cli/model_catalog.py) fetches that URL *instead of* the
master manifest for the openrouter block only — Nous Portal and everything else keep
resolving normally. This script generates that manifest from the **live** OpenRouter
catalog:

* curated flagships first (so the good models lead the picker),
* then every remaining tool-capable text model, newest first,
* "recommended" badge stays on the top entry (applied by Hermes itself).

Hermes still intersects the result with the live catalog and re-applies the `tools`
filter, so the manifest only needs to be a **superset** — retired ids self-clean on
every refresh, and a stale manifest can never break the picker.

## Install (3 steps, Windows/macOS/Linux)

```bash
# 1. put the script under ~/.hermes/scripts/ (anywhere works)
curl -o ~/.hermes/scripts/refresh_openrouter_catalog.py \
  https://raw.githubusercontent.com/donwrightdesigns/hermes-openrouter-full-picker/main/refresh_openrouter_catalog.py

# 2. generate the manifest (prints your exact config command)
python ~/.hermes/scripts/refresh_openrouter_catalog.py

# 3. wire the picker, restart Hermes, open /model
hermes config set model_catalog.providers.openrouter.url "file:///<absolute path to>/openrouter-full.json"
```

Multi-profile installs: add the same `model_catalog.providers.openrouter.url` line to
each `~/.hermes/profiles/<name>/config.yaml` (profiles with no config.yaml inherit the
global one automatically).

## Keep it fresh (optional)

Any scheduler works. Hermes cron example:

* every 6-12h, `no_agent: true`, script: `refresh_openrouter_catalog.py`, deliver: local

New OpenRouter models then appear in the picker within hours of release (6h cadence
tested live; the mimo-v2.6 trio landed same-day). Offline
runs leave the existing manifest untouched (exit 1, no clobber).

## Compatibility

* Hermes Agent v0.21.3 (uses `model_catalog.providers` override — present since the
  model-catalog manifest shipped). If your build lacks it, update Hermes.
* Reads `OPENROUTER_MODELS` from the installed repo for ordering only; nothing is
  written into the Hermes install. Uninstall = remove one config line.
* stdlib only, Python 3.9+.

## LICENSE

MIT — do whatever; attribution appreciated. If this unblocks you, pass the fix along to
someone else who's staring at a 34-model picker; that's the whole license.