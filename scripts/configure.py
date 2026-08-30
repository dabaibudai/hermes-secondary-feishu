#!/usr/bin/env python3
"""Securely manage multiple secondary Feishu bots without echoing secrets."""

from __future__ import annotations

import argparse
import getpass
import os
import re
import subprocess
import sys
from pathlib import Path


BOTS_KEY = "HERMES_SECONDARY_FEISHU_BOTS"
LEGACY_APP_ID_KEY = "HERMES_SECONDARY_FEISHU_APP_ID"
LEGACY_APP_SECRET_KEY = "HERMES_SECONDARY_FEISHU_APP_SECRET"
LEGACY_KEYS = {
    LEGACY_APP_ID_KEY,
    LEGACY_APP_SECRET_KEY,
    "HERMES_SECONDARY_FEISHU_DOMAIN",
    "HERMES_SECONDARY_FEISHU_CONNECTION_MODE",
    "HERMES_SECONDARY_FEISHU_ALLOWED_USERS",
    "HERMES_SECONDARY_FEISHU_ALLOW_ALL_USERS",
    "HERMES_SECONDARY_FEISHU_ENCRYPT_KEY",
    "HERMES_SECONDARY_FEISHU_VERIFICATION_TOKEN",
    "HERMES_SECONDARY_FEISHU_GROUP_POLICY",
    "HERMES_SECONDARY_FEISHU_BOT_OPEN_ID",
    "HERMES_SECONDARY_FEISHU_BOT_USER_ID",
    "HERMES_SECONDARY_FEISHU_BOT_NAME",
    "HERMES_SECONDARY_FEISHU_ALLOW_BOTS",
    "HERMES_SECONDARY_FEISHU_REQUIRE_MENTION",
}
_ALIAS_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")


def normalize_alias(value: str) -> str:
    alias = value.strip().lower().replace("_", "-")
    if not _ALIAS_RE.fullmatch(alias):
        raise ValueError(
            "Bot name must start with a letter and contain only lowercase "
            "letters, digits, or hyphens (maximum 32 characters)."
        )
    return alias


def platform_name_for(alias: str) -> str:
    return "feishu_secondary" if alias == "hermes2" else f"feishu_{alias.replace('-', '_')}"


def env_prefix_for(alias: str) -> str:
    return f"HERMES_SECONDARY_FEISHU_{alias.upper().replace('-', '_')}"


def validate_model_route(provider: str, model: str) -> tuple[str, str]:
    provider = provider.strip()
    model = model.strip()
    if not provider or not model:
        raise ValueError("Both provider and model IDs are required")
    if any(char.isspace() for char in provider + model):
        raise ValueError("Provider and model IDs cannot contain whitespace")
    return provider, model


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


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def update_env_file(path: Path, values: dict[str, str]) -> None:
    if any("\n" in value or "\r" in value for value in values.values()):
        raise ValueError("Environment values must be single-line strings")

    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(values)
    output: list[str] = []
    updated: set[str] = set()

    for line in lines:
        stripped = line.strip()
        key = stripped.split("=", 1)[0].strip() if "=" in stripped else ""
        if key in values:
            if key not in updated:
                output.append(f"{key}={remaining.pop(key)}")
                updated.add(key)
            continue
        output.append(line)

    if output and output[-1].strip():
        output.append("")
    output.extend(f"{key}={value}" for key, value in remaining.items())
    _atomic_write(path, output)


def remove_env_keys(path: Path, keys: set[str]) -> None:
    if not path.exists():
        return
    output: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        key = stripped.split("=", 1)[0].strip() if "=" in stripped else ""
        if key not in keys:
            output.append(line)
    _atomic_write(path, output)


def _atomic_write(path: Path, lines: list[str]) -> None:
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    temp_path.chmod(0o600)
    temp_path.replace(path)
    path.chmod(0o600)


def configured_aliases(values: dict[str, str]) -> list[str]:
    aliases: list[str] = []
    for raw_alias in values.get(BOTS_KEY, "").split(","):
        if not raw_alias.strip():
            continue
        try:
            alias = normalize_alias(raw_alias)
        except ValueError:
            continue
        if alias not in aliases:
            aliases.append(alias)

    if not aliases and (
        values.get(LEGACY_APP_ID_KEY) or values.get(LEGACY_APP_SECRET_KEY)
    ):
        aliases.append("hermes2")
    return aliases


def bot_values(
    alias: str,
    app_id: str,
    app_secret: str,
    domain: str,
    allowed: str,
    provider: str = "",
    model: str = "",
) -> dict[str, str]:
    prefix = env_prefix_for(alias)
    values = {
        f"{prefix}_APP_ID": app_id,
        f"{prefix}_APP_SECRET": app_secret,
        f"{prefix}_DOMAIN": domain,
        f"{prefix}_CONNECTION_MODE": "websocket",
        f"{prefix}_ALLOWED_USERS": allowed,
    }
    if provider or model:
        provider, model = validate_model_route(provider, model)
        values[f"{prefix}_PROVIDER"] = provider
        values[f"{prefix}_MODEL"] = model
    return values


def list_bots(env_path: Path) -> int:
    values = read_env_file(env_path)
    aliases = configured_aliases(values)
    if not aliases:
        print("No secondary Feishu bots configured.")
        return 0
    for alias in aliases:
        prefix = env_prefix_for(alias)
        configured = bool(
            (values.get(f"{prefix}_APP_ID") or (alias == "hermes2" and values.get(LEGACY_APP_ID_KEY)))
            and (
                values.get(f"{prefix}_APP_SECRET")
                or (alias == "hermes2" and values.get(LEGACY_APP_SECRET_KEY))
            )
        )
        provider = values.get(f"{prefix}_PROVIDER", "")
        model = values.get(f"{prefix}_MODEL", "")
        route = f"{provider}/{model}" if provider and model else "shared-default"
        print(
            f"{alias}: platform={platform_name_for(alias)}, "
            f"credentials={'ready' if configured else 'missing'}, model={route}"
        )
    return 0


def remove_bot(env_path: Path, alias: str) -> int:
    alias = normalize_alias(alias)
    values = read_env_file(env_path)
    aliases = configured_aliases(values)
    if alias not in aliases:
        print(f"Bot '{alias}' is not configured.")
        return 1

    aliases = [item for item in aliases if item != alias]
    prefix = env_prefix_for(alias)
    keys = {key for key in values if key.startswith(f"{prefix}_")}
    if alias == "hermes2":
        keys.update(LEGACY_KEYS.intersection(values))
    remove_env_keys(env_path, keys)
    update_env_file(env_path, {BOTS_KEY: ",".join(aliases)})
    print(f"Removed '{alias}'. Restart Hermes Gateway to apply the change.")
    return 0


def set_bot_model(
    env_path: Path,
    alias: str,
    provider: str,
    model: str,
) -> int:
    alias = normalize_alias(alias)
    values = read_env_file(env_path)
    if alias not in configured_aliases(values):
        print(f"Bot '{alias}' is not configured; nothing was changed.")
        return 1
    try:
        provider, model = validate_model_route(provider, model)
    except ValueError as exc:
        print(f"{exc}; nothing was changed.")
        return 1
    prefix = env_prefix_for(alias)
    update_env_file(
        env_path,
        {
            f"{prefix}_PROVIDER": provider,
            f"{prefix}_MODEL": model,
        },
    )
    print(f"Saved model route for '{alias}': {provider}/{model}")
    print("Restart Hermes Gateway to apply the change.")
    return 0


def clear_bot_model(env_path: Path, alias: str) -> int:
    alias = normalize_alias(alias)
    values = read_env_file(env_path)
    if alias not in configured_aliases(values):
        print(f"Bot '{alias}' is not configured; nothing was changed.")
        return 1
    prefix = env_prefix_for(alias)
    remove_env_keys(
        env_path,
        {f"{prefix}_PROVIDER", f"{prefix}_MODEL"},
    )
    print(f"Cleared model route for '{alias}'; it will use the shared default.")
    print("Restart Hermes Gateway to apply the change.")
    return 0


def configure_bot(
    env_path: Path,
    requested_alias: str | None = None,
    requested_app_id: str | None = None,
    secret_from_stdin: bool = False,
    requested_domain: str | None = None,
    requested_allowed_users: str | None = None,
    requested_provider: str | None = None,
    requested_model: str | None = None,
) -> int:
    values = read_env_file(env_path)
    aliases = configured_aliases(values)
    if aliases:
        print(f"Configured bots: {', '.join(aliases)}")

    default_alias = requested_alias or ("hermes2" if not aliases else "")
    prompt = f"Bot name{f' (default: {default_alias})' if default_alias else ''}: "
    raw_alias = requested_alias or input(prompt).strip() or default_alias
    try:
        alias = normalize_alias(raw_alias)
    except ValueError as exc:
        print(str(exc))
        return 1

    app_id = (requested_app_id or input("Secondary Feishu/Lark App ID: ")).strip()
    if secret_from_stdin:
        app_secret = sys.stdin.readline().strip()
    else:
        app_secret = getpass.getpass("Secondary App Secret (hidden): ").strip()
    if not app_id or not app_secret:
        print("App ID and App Secret are required; nothing was changed.")
        return 1

    primary_app_id = values.get("FEISHU_APP_ID", "")
    if primary_app_id and app_id == primary_app_id:
        print("This App ID belongs to the primary Feishu bot; nothing was changed.")
        return 1

    for existing_alias in aliases:
        if existing_alias == alias:
            continue
        existing_prefix = env_prefix_for(existing_alias)
        existing_id = values.get(f"{existing_prefix}_APP_ID", "")
        if existing_alias == "hermes2" and not existing_id:
            existing_id = values.get(LEGACY_APP_ID_KEY, "")
        if existing_id and app_id == existing_id:
            print(
                f"This App ID is already used by '{existing_alias}'; nothing was changed."
            )
            return 1

    domain = (
        requested_domain
        if requested_domain is not None
        else input("Tenant [feishu/lark] (default: feishu): ")
    ).strip().lower()
    if domain not in {"", "feishu", "lark"}:
        print("Tenant must be 'feishu' or 'lark'; nothing was changed.")
        return 1
    allowed_users = (
        requested_allowed_users
        if requested_allowed_users is not None
        else input("Allowed user Open IDs, comma-separated (blank = use pairing): ")
    ).strip()

    provider = (requested_provider or "").strip()
    model = (requested_model or "").strip()
    if provider or model:
        try:
            provider, model = validate_model_route(provider, model)
        except ValueError as exc:
            print(f"{exc}; nothing was changed.")
            return 1

    if alias not in aliases:
        aliases.append(alias)
    updates = {BOTS_KEY: ",".join(aliases)}
    updates.update(
        bot_values(
            alias,
            app_id,
            app_secret,
            domain or "feishu",
            allowed_users,
            provider,
            model,
        )
    )
    update_env_file(env_path, updates)

    print(f"Saved '{alias}' securely to {env_path}")
    print(f"Pairing platform: {platform_name_for(alias)}")
    print("Configure more bots before restarting, or restart once when finished.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", help="Bot name to add or update, e.g. hermes3")
    parser.add_argument("--app-id", help="Secondary Feishu/Lark App ID")
    parser.add_argument(
        "--secret-stdin",
        action="store_true",
        help="Read the App Secret from one stdin line without echoing it",
    )
    parser.add_argument("--domain", choices=("feishu", "lark"))
    parser.add_argument(
        "--allowed-users",
        help="Comma-separated Open IDs; use an empty value to require pairing",
    )
    parser.add_argument("--list", action="store_true", help="List configured bots")
    parser.add_argument("--remove", metavar="NAME", help="Remove one bot configuration")
    parser.add_argument(
        "--set-model",
        metavar="NAME",
        help="Persist a provider/model route for one configured bot",
    )
    parser.add_argument(
        "--clear-model",
        metavar="NAME",
        help="Return one configured bot to Hermes' shared default model",
    )
    parser.add_argument("--provider", help="Hermes provider ID for this bot")
    parser.add_argument("--model", help="Exact API model ID for this bot")
    args = parser.parse_args()

    env_path = default_env_path()
    if args.list:
        return list_bots(env_path)
    if args.remove:
        return remove_bot(env_path, args.remove)
    if args.set_model:
        return set_bot_model(
            env_path,
            args.set_model,
            args.provider or "",
            args.model or "",
        )
    if args.clear_model:
        return clear_bot_model(env_path, args.clear_model)
    return configure_bot(
        env_path,
        args.name,
        args.app_id,
        args.secret_stdin,
        args.domain,
        args.allowed_users,
        args.provider,
        args.model,
    )


if __name__ == "__main__":
    raise SystemExit(main())
