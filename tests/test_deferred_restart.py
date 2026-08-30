import tempfile
import unittest
from pathlib import Path

from scripts.deferred_restart import wait_for_response_sent


class DeferredRestartTest(unittest.TestCase):
    def test_detects_only_new_sent_response(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log = Path(temp_dir) / "gateway.log"
            log.write_text("Sending response old\n", encoding="utf-8")
            offset = log.stat().st_size
            with log.open("a", encoding="utf-8") as handle:
                handle.write("Sending response current\n")
            self.assertTrue(wait_for_response_sent(log, offset, 1))

    def test_times_out_without_response(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log = Path(temp_dir) / "gateway.log"
            log.write_text("tool call finished\n", encoding="utf-8")
            self.assertFalse(wait_for_response_sent(log, 0, 0))
