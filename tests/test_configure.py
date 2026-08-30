import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.configure import (
    BOTS_KEY,
    bot_values,
    configured_aliases,
    platform_name_for,
    read_env_file,
    remove_env_keys,
    update_env_file,
)


class ConfigureTest(unittest.TestCase):
    def test_adds_multiple_bots_without_touching_primary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "FEISHU_APP_ID=primary\nFEISHU_APP_SECRET=keep-me\n",
                encoding="utf-8",
            )
            updates = {BOTS_KEY: "hermes2,hermes3"}
            updates.update(bot_values("hermes2", "app-2", "secret-2", "feishu", ""))
            updates.update(bot_values("hermes3", "app-3", "secret-3", "lark", "ou_a"))
            update_env_file(env_path, updates)

            values = read_env_file(env_path)
            self.assertEqual(configured_aliases(values), ["hermes2", "hermes3"])
            self.assertEqual(values["FEISHU_APP_ID"], "primary")
            self.assertEqual(values["FEISHU_APP_SECRET"], "keep-me")
            self.assertEqual(values["HERMES_SECONDARY_FEISHU_HERMES3_APP_ID"], "app-3")
            self.assertEqual(env_path.stat().st_mode & 0o777, 0o600)

    def test_partial_update_preserves_other_values_and_removes_duplicates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "HERMES_SECONDARY_FEISHU_HERMES2_APP_ID=old\n"
                "HERMES_SECONDARY_FEISHU_HERMES2_APP_ID=duplicate\n"
                "HERMES_SECONDARY_FEISHU_HERMES2_APP_SECRET=keep-me\n",
                encoding="utf-8",
            )
            update_env_file(
                env_path,
                {"HERMES_SECONDARY_FEISHU_HERMES2_APP_ID": "new"},
            )

            content = env_path.read_text(encoding="utf-8")
            self.assertEqual(
                content.count("HERMES_SECONDARY_FEISHU_HERMES2_APP_ID="), 1
            )
            self.assertIn("HERMES_SECONDARY_FEISHU_HERMES2_APP_ID=new", content)
            self.assertIn(
                "HERMES_SECONDARY_FEISHU_HERMES2_APP_SECRET=keep-me", content
            )

    def test_remove_keys_keeps_other_bot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "HERMES_SECONDARY_FEISHU_HERMES2_APP_ID=app-2\n"
                "HERMES_SECONDARY_FEISHU_HERMES3_APP_ID=app-3\n",
                encoding="utf-8",
            )
            remove_env_keys(
                env_path, {"HERMES_SECONDARY_FEISHU_HERMES2_APP_ID"}
            )
            values = read_env_file(env_path)
            self.assertNotIn("HERMES_SECONDARY_FEISHU_HERMES2_APP_ID", values)
            self.assertEqual(
                values["HERMES_SECONDARY_FEISHU_HERMES3_APP_ID"], "app-3"
            )

    def test_platform_names_preserve_hermes2_compatibility(self):
        self.assertEqual(platform_name_for("hermes2"), "feishu_secondary")
        self.assertEqual(platform_name_for("hermes5"), "feishu_hermes5")

    def test_noninteractive_secret_from_stdin(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            script = Path(__file__).parents[1] / "scripts" / "configure.py"
            env = dict(os.environ, HERMES_HOME=temp_dir, PATH="")
            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--name",
                    "hermes2",
                    "--app-id",
                    "cli_test",
                    "--domain",
                    "feishu",
                    "--allowed-users",
                    "",
                    "--secret-stdin",
                ],
                input="secret-from-chat\n",
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            values = read_env_file(Path(temp_dir) / ".env")
            self.assertEqual(
                values["HERMES_SECONDARY_FEISHU_HERMES2_APP_SECRET"],
                "secret-from-chat",
            )
            self.assertNotIn("secret-from-chat", result.stdout)


if __name__ == "__main__":
    unittest.main()
