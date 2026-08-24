#!/usr/bin/env python3
"""Static repository validation that does not require Hermes to be installed."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = {
    "plugin.yaml",
    "adapter.py",
    "__init__.py",
    "README.md",
    "LICENSE",
}


missing = sorted(name for name in REQUIRED_FILES if not (ROOT / name).is_file())
if missing:
    raise SystemExit(f"Missing required files: {', '.join(missing)}")

manifest = (ROOT / "plugin.yaml").read_text(encoding="utf-8")
if "name: hermes-secondary-feishu" not in manifest:
    raise SystemExit("plugin.yaml has an unexpected name")
if "kind: platform" not in manifest:
    raise SystemExit("plugin.yaml kind must be platform")

expected = {
    "HERMES_SECONDARY_FEISHU_APP_ID",
    "HERMES_SECONDARY_FEISHU_APP_SECRET",
}
if not all(name in manifest for name in expected):
    raise SystemExit("plugin.yaml is missing required credential variables")

print("PLUGIN_STATIC_VALIDATION_OK")
