import asyncio
import os
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

try:
    from gateway.config import PlatformConfig
    import gateway.run  # Load dotenv before isolated environment patches.
    import gateway.platforms.feishu as feishu_module
    from gateway.platform_registry import PlatformEntry, platform_registry
    import lark_oapi.ws.client as ws_client_module
except ModuleNotFoundError as exc:
    raise unittest.SkipTest("Hermes runtime is required for adapter tests") from exc

from adapter import (
    BOTS_ENV,
    BotSpec,
    ModelRoute,
    SecondaryFeishuAdapter,
    check_requirements,
    env_prefix_for,
    load_bot_specs,
    platform_name_for,
    register,
    validate_config,
    _install_multi_client_ws_patch,
    _install_model_router,
    _normalize_command_text,
    _route_runtime,
    _run_isolated_feishu_ws_client,
    _THREAD_LOCAL_LOOP,
    _is_secondary_home_notice,
)


def make_spec(alias: str) -> BotSpec:
    return BotSpec(alias, platform_name_for(alias), env_prefix_for(alias))


def register_test_platform(spec: BotSpec) -> None:
    if not platform_registry.is_registered(spec.platform_name):
        platform_registry.register(
            PlatformEntry(
                name=spec.platform_name,
                label=spec.label,
                adapter_factory=lambda config: SecondaryFeishuAdapter(config, spec),
                check_fn=lambda: True,
            )
        )


class FakeContext:
    def __init__(self):
        self.entries = []

    def register_platform(self, **kwargs):
        self.entries.append(kwargs)


class SecondaryFeishuAdapterTest(unittest.TestCase):
    def test_unescapes_feishu_rich_post_slash_commands_only(self):
        self.assertEqual(
            _normalize_command_text(
                r"/model kimi\-for\-coding \-\-provider kimi\-coding"
            ),
            "/model kimi-for-coding --provider kimi-coding",
        )
        self.assertEqual(_normalize_command_text(r"normal \- text"), r"normal \- text")

    def test_per_bot_model_route_is_optional_and_exact(self):
        spec = make_spec("hermes2")
        with patch.dict(
            os.environ,
            {
                "HERMES_SECONDARY_FEISHU_HERMES2_PROVIDER": "kimi-coding",
                "HERMES_SECONDARY_FEISHU_HERMES2_MODEL": "kimi-for-coding",
            },
            clear=True,
        ):
            self.assertEqual(
                spec.model_route(),
                ModelRoute("kimi-coding", "kimi-for-coding"),
            )

        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(spec.model_route())

    def test_route_runtime_uses_hermes_provider_registry(self):
        route = ModelRoute("example-provider", "example-model")
        with patch(
            "hermes_cli.runtime_provider.resolve_runtime_provider",
            return_value={
                "provider": "canonical-provider",
                "api_key": "secret",
                "base_url": "https://example.invalid/v1",
                "api_mode": "openai_chat",
            },
        ) as resolver:
            runtime = _route_runtime(route, {"provider": "global"})

        resolver.assert_called_once_with(
            requested="example-provider",
            target_model="example-model",
        )
        self.assertEqual(runtime["provider"], "canonical-provider")
        self.assertEqual(runtime["api_mode"], "openai_chat")

    def test_model_router_changes_only_secondary_default_and_survives_reset(self):
        from gateway.platforms.base import EphemeralReply

        class FakeRunner:
            def __init__(self):
                self._session_model_overrides = {}

            def _session_key_for_source(self, source):
                return f"agent:main:{source.platform.value}:dm:chat"

            def _resolve_session_agent_runtime(
                self, *, source=None, session_key=None, user_config=None
            ):
                key = session_key or self._session_key_for_source(source)
                override = self._session_model_overrides.get(key)
                if override:
                    return override["model"], {"provider": override["provider"]}
                return "k3", {"provider": "kimi-coding"}

            async def _handle_reset_command(self, event):
                return EphemeralReply(
                    "✨ Session reset! Starting fresh.\n\n"
                    "◆ Model: `k3`\n◆ Provider: kimi-coding\n"
                    "◆ Context: 1.0M tokens (detected)\n✦ Tip: test"
                )

        secondary = SimpleNamespace(
            platform=SimpleNamespace(value="feishu_secondary")
        )
        primary = SimpleNamespace(platform=SimpleNamespace(value="feishu"))
        route = ModelRoute("kimi-coding", "kimi-for-coding")

        with patch("gateway.run.GatewayRunner", FakeRunner), patch(
            "hermes_cli.runtime_provider.resolve_runtime_provider",
            return_value={
                "provider": "kimi-coding",
                "api_key": "secret",
                "base_url": "https://api.kimi.com/coding",
                "api_mode": "anthropic_messages",
            },
        ), patch(
            "adapter._format_route_info",
            return_value=(
                "◆ Model: `kimi-for-coding`\n◆ Provider: kimi-coding\n"
                "◆ Context: 256K tokens (detected)"
            ),
        ):
            _install_model_router({"feishu_secondary": route})
            runner = FakeRunner()
            self.assertEqual(
                runner._resolve_session_agent_runtime(source=secondary)[0],
                "kimi-for-coding",
            )
            self.assertEqual(
                runner._resolve_session_agent_runtime(source=primary)[0],
                "k3",
            )

            key = runner._session_key_for_source(secondary)
            runner._session_model_overrides[key] = {
                "model": "temporary-model",
                "provider": "temporary-provider",
            }
            self.assertEqual(
                runner._resolve_session_agent_runtime(source=secondary)[0],
                "temporary-model",
            )
            runner._session_model_overrides.clear()
            reply = asyncio.run(
                runner._handle_reset_command(SimpleNamespace(source=secondary))
            )
            self.assertIn("Model: `kimi-for-coding`", reply)

    def test_suppresses_only_secondary_home_notice(self):
        platforms = {"feishu_secondary", "feishu_baymax"}
        notice = "📬 No home channel is set for Feishu_Baymax."
        self.assertTrue(
            _is_secondary_home_notice("feishu_baymax", notice, platforms)
        )
        self.assertFalse(_is_secondary_home_notice("feishu", notice, platforms))
        self.assertFalse(
            _is_secondary_home_notice(
                "feishu_baymax", "Pairing approval required", platforms
            )
        )

    def test_installs_thread_isolated_lark_runtime(self):
        _install_multi_client_ws_patch()
        self.assertIs(
            feishu_module._run_official_feishu_ws_client,
            _run_isolated_feishu_ws_client,
        )
        self.assertIs(ws_client_module.loop, _THREAD_LOCAL_LOOP)

    def test_two_ws_threads_keep_distinct_event_loops(self):
        barrier = threading.Barrier(2)
        loop_ids = []
        errors = []

        class FakeAdapter:
            _ws_ping_interval = None
            _ws_ping_timeout = None
            _ws_reconnect_nonce = 0
            _ws_reconnect_interval = 1
            _ws_thread_loop = None

        class FakeClient:
            def start(self):
                async def current_loop_id():
                    return id(asyncio.get_running_loop())

                first = _THREAD_LOCAL_LOOP.run_until_complete(current_loop_id())
                barrier.wait(timeout=2)
                second = _THREAD_LOCAL_LOOP.run_until_complete(current_loop_id())
                if first != second:
                    raise AssertionError("Client switched event loops")
                loop_ids.append(first)

        def run_client():
            try:
                _run_isolated_feishu_ws_client(FakeClient(), FakeAdapter())
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=run_client) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=3)

        self.assertEqual(errors, [])
        self.assertEqual(len(loop_ids), 2)
        self.assertEqual(len(set(loop_ids)), 2)

    def test_multiple_bots_have_isolated_credentials_platforms_and_cache(self):
        with tempfile.TemporaryDirectory() as home, patch.dict(
            os.environ,
            {
                "HERMES_HOME": home,
                BOTS_ENV: "hermes2,hermes3",
                "HERMES_SECONDARY_FEISHU_HERMES2_APP_ID": "app-2",
                "HERMES_SECONDARY_FEISHU_HERMES2_APP_SECRET": "secret-2",
                "HERMES_SECONDARY_FEISHU_HERMES3_APP_ID": "app-3",
                "HERMES_SECONDARY_FEISHU_HERMES3_APP_SECRET": "secret-3",
                "HERMES_SECONDARY_FEISHU_HERMES3_ALLOWED_USERS": "ou_a,ou_b",
            },
            clear=True,
        ):
            specs = load_bot_specs()
            for spec in specs:
                register_test_platform(spec)
            adapters = [SecondaryFeishuAdapter(PlatformConfig(), spec) for spec in specs]

        self.assertEqual(
            [adapter.platform.value for adapter in adapters],
            ["feishu_secondary", "feishu_hermes3"],
        )
        self.assertEqual([adapter._app_id for adapter in adapters], ["app-2", "app-3"])
        self.assertEqual(adapters[1]._allowed_group_users, {"ou_a", "ou_b"})
        self.assertEqual(
            [adapter._dedup_state_path.name for adapter in adapters],
            [
                "feishu_secondary_seen_message_ids.json",
                "feishu_hermes3_seen_message_ids.json",
            ],
        )

    def test_legacy_hermes2_variables_still_work(self):
        with patch.dict(
            os.environ,
            {
                "HERMES_SECONDARY_FEISHU_APP_ID": "legacy-app",
                "HERMES_SECONDARY_FEISHU_APP_SECRET": "legacy-secret",
            },
            clear=True,
        ):
            specs = load_bot_specs()
            self.assertEqual([spec.alias for spec in specs], ["hermes2"])
            self.assertEqual(specs[0].credentials(), ("legacy-app", "legacy-secret"))
            self.assertTrue(check_requirements())
            self.assertTrue(validate_config(PlatformConfig()))

    def test_duplicate_app_id_registers_only_first_bot(self):
        with patch.dict(
            os.environ,
            {
                BOTS_ENV: "hermes2,hermes3",
                "HERMES_SECONDARY_FEISHU_HERMES2_APP_ID": "same-app",
                "HERMES_SECONDARY_FEISHU_HERMES2_APP_SECRET": "secret-2",
                "HERMES_SECONDARY_FEISHU_HERMES3_APP_ID": "same-app",
                "HERMES_SECONDARY_FEISHU_HERMES3_APP_SECRET": "secret-3",
            },
            clear=True,
        ):
            context = FakeContext()
            register(context)

        self.assertEqual(len(context.entries), 1)
        self.assertEqual(context.entries[0]["name"], "feishu_secondary")

    def test_primary_app_id_is_never_registered_as_secondary(self):
        with patch.dict(
            os.environ,
            {
                "FEISHU_APP_ID": "primary-app",
                BOTS_ENV: "hermes2",
                "HERMES_SECONDARY_FEISHU_HERMES2_APP_ID": "primary-app",
                "HERMES_SECONDARY_FEISHU_HERMES2_APP_SECRET": "secret-2",
            },
            clear=True,
        ):
            context = FakeContext()
            register(context)

        self.assertEqual(context.entries, [])


if __name__ == "__main__":
    unittest.main()
