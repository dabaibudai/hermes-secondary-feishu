#!/usr/bin/env python3
"""Securely configure the secondary Feishu plugin without echoing secrets."""

from __future__ import annotations

import getpass
import os
import subprocess
from pathlib import Path


KEYS = (
    "HERMES_SECONDARY_FEISHU_APP_ID",
    "HERMES_SECONDARY_FEISHU_APP_SECRET",
    "HERMES_SECONDARY_FEISHU_DOMAIN",
    "HERMES_SECONDARY_FEISHU_CONNECTION_MODE",
    "HERMES_SECONDARY_FEISHU_ALLOWED_USERS",
)


def default_env_path() -> Path:
    try:
        result = subprocess.run(
            ["hermes", "config", "env-path"],
            check=True,
            capture_output=True,
            text=True,
        )
        value = result.stdout.strip().splitlines()[-1].strip()
        if value:
            return Path(value).expanduser()
    except (FileNotFoundError, subprocess.CalledProcessError, IndexError):
        pass

    hermes_home = Path(os.getenv("HERMES_HOME", "~/.hermes")).expanduser()
    return hermes_home / ".env"


def update_env_file(path: Path, values: dict[str, str]) -> None:
    if any("\n" in value or "\r" in value for value in values.values()):
        raise ValueError("Environment values must be single-line strings")

    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(values)
    output: list[str] = []

    for line in lines:
        stripped = line.strip()
        replaced = False
        for key in KEYS:
            if key in remaining and stripped.startswith(f"{key}="):
                output.append(f"{key}={remaining.pop(key)}")
                replaced = True
                break
        if not replaced:
            output.append(line)

    if output and output[-1].strip():
        output.append("")
    output.extend(f"{key}={value}" for key, value in remaining.items())

    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    temp_path.chmod(0o600)
    temp_path.replace(path)
    path.chmod(0o600)


def main() -> int:
    print("Configure Hermes Secondary Feishu")
    app_id = input("Secondary Feishu/Lark App ID: ").strip()
    app_secret = getpass.getpass("Secondary App Secret (hidden): ").strip()
    if not app_id or not app_secret:
        print("App ID and App Secret are required; nothing was changed.")
        return 1

    domain = input("Tenant [feishu/lark] (default: feishu): ").strip().lower()
    if domain not in {"", "feishu", "lark"}:
        print("Tenant must be 'feishu' or 'lark'; nothing was changed.")
        return 1
    domain = domain or "feishu"
    allowed_users = input(
        "Allowed user Open IDs, comma-separated (blank = use pairing): "
    ).strip()

    env_path = default_env_path()
    update_env_file(
        env_path,
        {
            "HERMES_SECONDARY_FEISHU_APP_ID": app_id,
            "HERMES_SECONDARY_FEISHU_APP_SECRET": app_secret,
            "HERMES_SECONDARY_FEISHU_DOMAIN": domain,
            "HERMES_SECONDARY_FEISHU_CONNECTION_MODE": "websocket",
            "HERMES_SECONDARY_FEISHU_ALLOWED_USERS": allowed_users,
        },
    )
    print(f"Saved securely to {env_path}")
    print("Next: complete the Feishu console checklist, then restart Hermes Gateway.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
