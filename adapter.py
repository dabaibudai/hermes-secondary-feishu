"""Native multi-bot Feishu platform adapter for Hermes Agent."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, replace

from gateway.config import Platform, PlatformConfig
from gateway.platforms.feishu import (
    FeishuAdapter,
    FeishuAdapterSettings,
    check_feishu_requirements,
)
from hermes_constants import get_hermes_home


logger = logging.getLogger(__name__)

BOTS_ENV = "HERMES_SECONDARY_FEISHU_BOTS"
PLATFORM_NAME = "feishu_secondary"
APP_ID_ENV = "HERMES_SECONDARY_FEISHU_APP_ID"
APP_SECRET_ENV = "HERMES_SECONDARY_FEISHU_APP_SECRET"
ALLOWED_USERS_ENV = "HERMES_SECONDARY_FEISHU_ALLOWED_USERS"
ALLOW_ALL_USERS_ENV = "HERMES_SECONDARY_FEISHU_ALLOW_ALL_USERS"
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
    # Preserve the original Hermes2 platform and its existing session keys.
    return PLATFORM_NAME if alias == "hermes2" else f"feishu_{alias.replace('-', '_')}"


def env_prefix_for(alias: str) -> str:
    suffix = alias.upper().replace("-", "_")
    return f"HERMES_SECONDARY_FEISHU_{suffix}"


@dataclass(frozen=True)
class BotSpec:
    alias: str
    platform_name: str
    env_prefix: str

    @property
    def label(self) -> str:
        return f"Feishu {self.alias}"

    def env_name(self, suffix: str) -> str:
        return f"{self.env_prefix}_{suffix}"

    def value(self, suffix: str, default: str = "") -> str:
        value = os.getenv(self.env_name(suffix))
        if value is not None and value.strip():
            return value.strip()

        # Version 1 used singular variables for Hermes2. Keep them readable.
        if self.alias == "hermes2":
            legacy_name = f"HERMES_SECONDARY_FEISHU_{suffix}"
            legacy_value = os.getenv(legacy_name)
            if legacy_value is not None and legacy_value.strip():
                return legacy_value.strip()
        return default

    @property
    def app_id_env(self) -> str:
        return self.env_name("APP_ID")

    @property
    def app_secret_env(self) -> str:
        return self.env_name("APP_SECRET")

    @property
    def allowed_users_env(self) -> str:
        current = self.env_name("ALLOWED_USERS")
        if self.alias == "hermes2" and not os.getenv(current) and os.getenv(ALLOWED_USERS_ENV):
            return ALLOWED_USERS_ENV
        return current

    @property
    def allow_all_env(self) -> str:
        current = self.env_name("ALLOW_ALL_USERS")
        if self.alias == "hermes2" and not os.getenv(current) and os.getenv(ALLOW_ALL_USERS_ENV):
            return ALLOW_ALL_USERS_ENV
        return current

    @property
    def required_env(self) -> list[str]:
        if self.alias == "hermes2" and not os.getenv(self.app_id_env) and os.getenv(APP_ID_ENV):
            return [APP_ID_ENV, APP_SECRET_ENV]
        return [self.app_id_env, self.app_secret_env]

    def credentials(self, config: PlatformConfig | None = None) -> tuple[str, str]:
        extra = getattr(config, "extra", {}) or {}
        app_id = self.value("APP_ID", str(extra.get("app_id") or "")).strip()
        app_secret = self.value(
            "APP_SECRET", str(extra.get("app_secret") or "")
        ).strip()
        return app_id, app_secret


def load_bot_specs() -> list[BotSpec]:
    raw_aliases = os.getenv(BOTS_ENV, "")
    aliases: list[str] = []
    seen: set[str] = set()

    for raw_alias in raw_aliases.split(","):
        if not raw_alias.strip():
            continue
        try:
            alias = normalize_alias(raw_alias)
        except ValueError as exc:
            logger.error("Ignoring invalid secondary Feishu bot name %r: %s", raw_alias, exc)
            continue
        if alias not in seen:
            seen.add(alias)
            aliases.append(alias)

    # Automatic backward compatibility for installations made before v2.
    if not aliases and (os.getenv(APP_ID_ENV) or os.getenv(APP_SECRET_ENV)):
        aliases.append("hermes2")

    return [
        BotSpec(
            alias=alias,
            platform_name=platform_name_for(alias),
            env_prefix=env_prefix_for(alias),
        )
        for alias in aliases
    ]


def _env_bool(spec: BotSpec, suffix: str, default: bool) -> bool:
    value = spec.value(suffix)
    if not value:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _env_list(spec: BotSpec, suffix: str) -> frozenset[str]:
    return frozenset(
        item.strip() for item in spec.value(suffix).split(",") if item.strip()
    )


class SecondaryFeishuAdapter(FeishuAdapter):
    """Reuse Hermes' native Feishu UI for one configured bot instance."""

    def __init__(self, config: PlatformConfig, spec: BotSpec | None = None):
        self.bot_spec = spec or BotSpec(
            alias="hermes2",
            platform_name=PLATFORM_NAME,
            env_prefix=env_prefix_for("hermes2"),
        )
        super().__init__(config)
        self.platform = Platform(self.bot_spec.platform_name)

        self._dedup_state_path = (
            get_hermes_home()
            / f"{self.bot_spec.platform_name}_seen_message_ids.json"
        )
        self._seen_message_ids.clear()
        self._seen_message_order.clear()
        self._load_seen_message_ids()

    def _load_settings(self, extra: dict) -> FeishuAdapterSettings:
        spec = self.bot_spec
        merged = dict(extra or {})
        merged["app_id"] = spec.value("APP_ID", str(merged.get("app_id") or ""))
        merged["app_secret"] = spec.value(
            "APP_SECRET", str(merged.get("app_secret") or "")
        )
        merged["domain"] = spec.value(
            "DOMAIN", str(merged.get("domain") or "feishu")
        )
        merged["connection_mode"] = spec.value(
            "CONNECTION_MODE", str(merged.get("connection_mode") or "websocket")
        )

        settings = FeishuAdapter._load_settings(merged)
        return replace(
            settings,
            encrypt_key=spec.value("ENCRYPT_KEY"),
            verification_token=spec.value("VERIFICATION_TOKEN"),
            group_policy=spec.value("GROUP_POLICY", "allowlist").lower(),
            allowed_group_users=_env_list(spec, "ALLOWED_USERS"),
            bot_open_id=spec.value("BOT_OPEN_ID"),
            bot_user_id=spec.value("BOT_USER_ID"),
            bot_name=spec.value("BOT_NAME"),
            allow_bots=spec.value("ALLOW_BOTS", "none").lower(),
            require_mention=_env_bool(spec, "REQUIRE_MENTION", True),
        )


def check_requirements(spec: BotSpec | None = None) -> bool:
    candidates = [spec] if spec else load_bot_specs()
    return check_feishu_requirements() and any(
        bool(candidate and all(candidate.credentials())) for candidate in candidates
    )


def validate_config(config: PlatformConfig, spec: BotSpec | None = None) -> bool:
    candidates = [spec] if spec else load_bot_specs()
    return check_feishu_requirements() and any(
        bool(candidate and all(candidate.credentials(config))) for candidate in candidates
    )


def is_connected(config: PlatformConfig, spec: BotSpec | None = None) -> bool:
    candidates = [spec] if spec else load_bot_specs()
    return any(
        bool(candidate and all(candidate.credentials(config))) for candidate in candidates
    )


def register(ctx) -> None:
    configured_app_ids: set[str] = set()
    primary_app_id = os.getenv("FEISHU_APP_ID", "").strip()

    for spec in load_bot_specs():
        app_id, _ = spec.credentials()
        if app_id and app_id == primary_app_id:
            logger.error(
                "Skipping %s: it reuses the primary Feishu App ID",
                spec.alias,
            )
            continue
        if app_id and app_id in configured_app_ids:
            logger.error(
                "Skipping %s: another secondary bot uses the same Feishu App ID",
                spec.alias,
            )
            continue
        if app_id:
            configured_app_ids.add(app_id)

        ctx.register_platform(
            name=spec.platform_name,
            label=spec.label,
            adapter_factory=lambda config, current=spec: SecondaryFeishuAdapter(
                config, current
            ),
            check_fn=lambda current=spec: check_requirements(current),
            validate_config=lambda config, current=spec: validate_config(
                config, current
            ),
            is_connected=lambda config, current=spec: is_connected(config, current),
            required_env=spec.required_env,
            allowed_users_env=spec.allowed_users_env,
            allow_all_env=spec.allow_all_env,
            max_message_length=8000,
            pii_safe=True,
            emoji="💬",
            platform_hint=(
                f"You are chatting through the secondary Feishu/Lark bot "
                f"'{spec.alias}'. Markdown, images, files, message editing, "
                "and progress updates are supported."
            ),
        )
