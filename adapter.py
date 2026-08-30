"""Native multi-bot Feishu platform adapter for Hermes Agent."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import threading
from dataclasses import dataclass, replace

from gateway.config import Platform, PlatformConfig
from gateway.platforms.feishu import (
    FeishuAdapter,
    FeishuAdapterSettings,
    check_feishu_requirements,
)
from hermes_constants import get_hermes_home


logger = logging.getLogger(__name__)

_WS_RUNTIME_LOCK = threading.Lock()
_WS_THREAD_STATE = threading.local()
_ORIGINAL_WS_CONNECT = None


class _ThreadLocalLoopProxy:
    """Route the Lark SDK's module-global loop calls to each WS thread."""

    @staticmethod
    def _current() -> asyncio.AbstractEventLoop:
        loop = getattr(_WS_THREAD_STATE, "loop", None)
        return loop if loop is not None else asyncio.get_event_loop()

    def run_until_complete(self, awaitable):
        return self._current().run_until_complete(awaitable)

    def create_task(self, awaitable):
        return self._current().create_task(awaitable)


_THREAD_LOCAL_LOOP = _ThreadLocalLoopProxy()


async def _thread_local_ws_connect(*args, **kwargs):
    adapter = getattr(_WS_THREAD_STATE, "adapter", None)
    if adapter is not None:
        if adapter._ws_ping_interval is not None and "ping_interval" not in kwargs:
            kwargs["ping_interval"] = adapter._ws_ping_interval
        if adapter._ws_ping_timeout is not None and "ping_timeout" not in kwargs:
            kwargs["ping_timeout"] = adapter._ws_ping_timeout
    if _ORIGINAL_WS_CONNECT is None:
        raise RuntimeError("Original Lark websocket connector is unavailable")
    return await _ORIGINAL_WS_CONNECT(*args, **kwargs)


def _run_isolated_feishu_ws_client(ws_client, adapter) -> None:
    """Run one official Lark client without sharing its loop with peers."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _WS_THREAD_STATE.loop = loop
    _WS_THREAD_STATE.adapter = adapter
    adapter._ws_thread_loop = loop
    original_configure = getattr(ws_client, "_configure", None)

    def configure_with_overrides(conf):
        if original_configure is None:
            raise RuntimeError("Lark websocket client has no _configure method")
        result = original_configure(conf)
        setattr(ws_client, "_reconnect_nonce", adapter._ws_reconnect_nonce)
        setattr(ws_client, "_reconnect_interval", adapter._ws_reconnect_interval)
        if adapter._ws_ping_interval is not None:
            setattr(ws_client, "_ping_interval", adapter._ws_ping_interval)
        return result

    if original_configure is not None:
        setattr(ws_client, "_configure", configure_with_overrides)
    try:
        ws_client.start()
    except Exception:
        logger.debug("Feishu websocket thread exited", exc_info=True)
    finally:
        if original_configure is not None:
            setattr(ws_client, "_configure", original_configure)
        pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()
        adapter._ws_thread_loop = None
        _WS_THREAD_STATE.__dict__.clear()


def _install_multi_client_ws_patch() -> None:
    """Make the official Lark websocket SDK safe for concurrent bot clients."""
    global _ORIGINAL_WS_CONNECT

    import gateway.platforms.feishu as feishu_module
    import lark_oapi.ws.client as ws_client_module

    with _WS_RUNTIME_LOCK:
        if getattr(feishu_module, "_secondary_multi_client_patch", False):
            return
        _ORIGINAL_WS_CONNECT = ws_client_module.websockets.connect
        ws_client_module.loop = _THREAD_LOCAL_LOOP
        ws_client_module.websockets.connect = _thread_local_ws_connect
        feishu_module._run_official_feishu_ws_client = _run_isolated_feishu_ws_client
        feishu_module._secondary_multi_client_patch = True

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
    _install_multi_client_ws_patch()
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
                "and progress updates are supported. This bot is chat-only by "
                "default; do not suggest /sethome unless the user explicitly "
                "wants cron results delivered here."
            ),
        )
