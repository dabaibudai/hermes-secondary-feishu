"""Native secondary Feishu platform adapter for Hermes Agent."""

from __future__ import annotations

import os
from dataclasses import replace

from gateway.config import Platform, PlatformConfig
from gateway.platforms.feishu import (
    FeishuAdapter,
    FeishuAdapterSettings,
    check_feishu_requirements,
)
from hermes_constants import get_hermes_home


PLATFORM_NAME = "feishu_secondary"
APP_ID_ENV = "HERMES_SECONDARY_FEISHU_APP_ID"
APP_SECRET_ENV = "HERMES_SECONDARY_FEISHU_APP_SECRET"
ALLOWED_USERS_ENV = "HERMES_SECONDARY_FEISHU_ALLOWED_USERS"
ALLOW_ALL_USERS_ENV = "HERMES_SECONDARY_FEISHU_ALLOW_ALL_USERS"


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str) -> frozenset[str]:
    return frozenset(
        item.strip() for item in os.getenv(name, "").split(",") if item.strip()
    )


def _credentials(config: PlatformConfig | None = None) -> tuple[str, str]:
    extra = getattr(config, "extra", {}) or {}
    app_id = str(os.getenv(APP_ID_ENV) or extra.get("app_id") or "").strip()
    app_secret = str(
        os.getenv(APP_SECRET_ENV) or extra.get("app_secret") or ""
    ).strip()
    return app_id, app_secret


class SecondaryFeishuAdapter(FeishuAdapter):
    """Reuse Hermes' native Feishu UI while keeping a separate bot identity."""

    @staticmethod
    def _load_settings(extra: dict) -> FeishuAdapterSettings:
        merged = dict(extra or {})
        merged["app_id"] = os.getenv(APP_ID_ENV) or merged.get("app_id", "")
        merged["app_secret"] = os.getenv(APP_SECRET_ENV) or merged.get(
            "app_secret", ""
        )
        merged["domain"] = os.getenv(
            "HERMES_SECONDARY_FEISHU_DOMAIN", merged.get("domain", "feishu")
        )
        merged["connection_mode"] = os.getenv(
            "HERMES_SECONDARY_FEISHU_CONNECTION_MODE",
            merged.get("connection_mode", "websocket"),
        )

        settings = FeishuAdapter._load_settings(merged)
        return replace(
            settings,
            encrypt_key=os.getenv("HERMES_SECONDARY_FEISHU_ENCRYPT_KEY", ""),
            verification_token=os.getenv(
                "HERMES_SECONDARY_FEISHU_VERIFICATION_TOKEN", ""
            ),
            group_policy=os.getenv(
                "HERMES_SECONDARY_FEISHU_GROUP_POLICY", "allowlist"
            ).strip().lower(),
            allowed_group_users=_env_list(ALLOWED_USERS_ENV),
            bot_open_id=os.getenv("HERMES_SECONDARY_FEISHU_BOT_OPEN_ID", "").strip(),
            bot_user_id=os.getenv("HERMES_SECONDARY_FEISHU_BOT_USER_ID", "").strip(),
            bot_name=os.getenv("HERMES_SECONDARY_FEISHU_BOT_NAME", "").strip(),
            allow_bots=os.getenv(
                "HERMES_SECONDARY_FEISHU_ALLOW_BOTS", "none"
            ).strip().lower(),
            require_mention=_env_bool(
                "HERMES_SECONDARY_FEISHU_REQUIRE_MENTION", True
            ),
        )

    def __init__(self, config: PlatformConfig):
        super().__init__(config)
        self.platform = Platform(PLATFORM_NAME)

        # Each bot keeps its own persistent deduplication cache.
        self._dedup_state_path = (
            get_hermes_home() / "feishu_secondary_seen_message_ids.json"
        )
        self._seen_message_ids.clear()
        self._seen_message_order.clear()
        self._load_seen_message_ids()


def check_requirements() -> bool:
    app_id, app_secret = _credentials()
    return check_feishu_requirements() and bool(app_id and app_secret)


def validate_config(config: PlatformConfig) -> bool:
    app_id, app_secret = _credentials(config)
    return check_feishu_requirements() and bool(app_id and app_secret)


def is_connected(config: PlatformConfig) -> bool:
    app_id, app_secret = _credentials(config)
    return bool(app_id and app_secret)


def register(ctx) -> None:
    ctx.register_platform(
        name=PLATFORM_NAME,
        label="Feishu Secondary",
        adapter_factory=lambda config: SecondaryFeishuAdapter(config),
        check_fn=check_requirements,
        validate_config=validate_config,
        is_connected=is_connected,
        required_env=[APP_ID_ENV, APP_SECRET_ENV],
        allowed_users_env=ALLOWED_USERS_ENV,
        allow_all_env=ALLOW_ALL_USERS_ENV,
        max_message_length=8000,
        pii_safe=True,
        emoji="💬",
        platform_hint=(
            "You are chatting through a secondary Feishu/Lark bot. "
            "Markdown, images, files, message editing, and progress updates are supported."
        ),
    )
