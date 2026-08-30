import os
import tempfile
import unittest
from unittest.mock import patch

try:
    from gateway.config import PlatformConfig
    from gateway.platform_registry import PlatformEntry, platform_registry
except ModuleNotFoundError as exc:
    raise unittest.SkipTest("Hermes runtime is required for adapter tests") from exc

from adapter import (
    BOTS_ENV,
    BotSpec,
    SecondaryFeishuAdapter,
    check_requirements,
    env_prefix_for,
    load_bot_specs,
    platform_name_for,
    register,
    validate_config,
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
