import tempfile
import unittest
from pathlib import Path

from scripts.configure import update_env_file


class ConfigureTest(unittest.TestCase):
    def test_updates_only_secondary_variables(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "FEISHU_APP_ID=primary\n"
                "FEISHU_APP_SECRET=keep-me\n"
                "HERMES_SECONDARY_FEISHU_APP_ID=old\n",
                encoding="utf-8",
            )

            update_env_file(
                env_path,
                {
                    "HERMES_SECONDARY_FEISHU_APP_ID": "secondary",
                    "HERMES_SECONDARY_FEISHU_APP_SECRET": "secret",
                },
            )

            content = env_path.read_text(encoding="utf-8")
            self.assertIn("FEISHU_APP_ID=primary", content)
            self.assertIn("FEISHU_APP_SECRET=keep-me", content)
            self.assertIn("HERMES_SECONDARY_FEISHU_APP_ID=secondary", content)
            self.assertIn("HERMES_SECONDARY_FEISHU_APP_SECRET=secret", content)
            self.assertEqual(env_path.stat().st_mode & 0o777, 0o600)

    def test_partial_update_preserves_other_secondary_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "HERMES_SECONDARY_FEISHU_APP_ID=old\n"
                "HERMES_SECONDARY_FEISHU_APP_SECRET=keep-me\n",
                encoding="utf-8",
            )

            update_env_file(
                env_path,
                {"HERMES_SECONDARY_FEISHU_APP_ID": "new"},
            )

            content = env_path.read_text(encoding="utf-8")
            self.assertIn("HERMES_SECONDARY_FEISHU_APP_ID=new", content)
            self.assertIn("HERMES_SECONDARY_FEISHU_APP_SECRET=keep-me", content)


if __name__ == "__main__":
    unittest.main()
