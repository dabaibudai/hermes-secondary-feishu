import os
import tempfile
import unittest
from unittest.mock import patch

from gateway.config import PlatformConfig
from gateway.platform_registry import PlatformEntry, platform_registry

from adapter import (
    PLATFORM_NAME,
    SecondaryFeishuAdapter,
    check_requirements,
    validate_config,
)


class SecondaryFeishuAdapterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not platform_registry.is_registered(PLATFORM_NAME):
            platform_registry.register(
                PlatformEntry(
                    name=PLATFORM_NAME,
                    label="Feishu Secondary",
                    adapter_factory=lambda config: SecondaryFeishuAdapter(config),
                    check_fn=lambda: True,
                )
            )

    def test_secondary_credentials_and_platform_are_isolated(self):
        with tempfile.TemporaryDirectory() as home, patch.dict(
            os.environ,
            {
                "HERMES_HOME": home,
                "FEISHU_APP_ID": "primary-app",
                "FEISHU_APP_SECRET": "primary-secret",
                "HERMES_SECONDARY_FEISHU_APP_ID": "secondary-app",
                "HERMES_SECONDARY_FEISHU_APP_SECRET": "secondary-secret",
                "HERMES_SECONDARY_FEISHU_ALLOWED_USERS": "ou_a,ou_b",
            },
            clear=False,
        ):
            adapter = SecondaryFeishuAdapter(PlatformConfig())

        self.assertEqual(adapter.platform.value, PLATFORM_NAME)
        self.assertEqual(adapter._app_id, "secondary-app")
        self.assertEqual(adapter._app_secret, "secondary-secret")
        self.assertEqual(adapter._allowed_group_users, {"ou_a", "ou_b"})
        self.assertEqual(
            adapter._dedup_state_path.name,
            "feishu_secondary_seen_message_ids.json",
        )

    def test_requirement_and_config_validation(self):
        with patch.dict(
            os.environ,
            {
                "HERMES_SECONDARY_FEISHU_APP_ID": "secondary-app",
                "HERMES_SECONDARY_FEISHU_APP_SECRET": "secondary-secret",
            },
            clear=False,
        ):
            self.assertTrue(check_requirements())
            self.assertTrue(validate_config(PlatformConfig()))


if __name__ == "__main__":
    unittest.main()
