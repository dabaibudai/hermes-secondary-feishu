#!/usr/bin/env python3
"""Static repository validation that does not require Hermes to be installed."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = {
    "plugin.yaml",
    "SKILL.md",
    "adapter.py",
    "__init__.py",
    "README.md",
    "LICENSE",
    "scripts/configure.py",
    "scripts/deferred_restart.py",
}


missing = sorted(name for name in REQUIRED_FILES if not (ROOT / name).is_file())
if missing:
    raise SystemExit(f"Missing required files: {', '.join(missing)}")

manifest = (ROOT / "plugin.yaml").read_text(encoding="utf-8")
if "name: hermes-secondary-feishu" not in manifest:
    raise SystemExit("plugin.yaml has an unexpected name")
if "kind: platform" not in manifest:
    raise SystemExit("plugin.yaml kind must be platform")
if "version: 2.1.0" not in manifest:
    raise SystemExit("plugin.yaml version must match the per-bot routing release")

adapter = (ROOT / "adapter.py").read_text(encoding="utf-8")
if "_install_model_router" not in adapter:
    raise SystemExit("adapter.py must install persistent per-bot model routing")

skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
if "--set-model" not in skill or "--global" not in skill:
    raise SystemExit("SKILL.md must explain safe per-bot model configuration")

print("PLUGIN_STATIC_VALIDATION_OK")
