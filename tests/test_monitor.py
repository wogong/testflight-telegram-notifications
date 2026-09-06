import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

import monitor


class MonitorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        state = patch.object(monitor, "STATE_FILE", Path(temporary.name) / "state.json")
        state.start()
        self.addCleanup(state.stop)
        self.cfg = {
            "url": "https://testflight.apple.com/join/XXXXXXXX",
            "tg_token": "test-token",
            "tg_chat_id": "test-chat",
            "timeout": 20,
        }

    def test_closed_and_unrecognized_pages(self):
        for marker in monitor.FULL_MARKERS:
            with self.subTest(marker=marker):
                self.assertFalse(monitor.check_availability(f"TestFlight {marker}")[0])
        self.assertFalse(monitor.check_availability("Service unavailable")[0])

    @patch.object(monitor, "send_telegram")
    @patch.object(monitor, "fetch")
    def test_notifies_on_first_open_and_reopening_only(self, fetch, send):
        fetch.side_effect = [
            "Join the Example beta on TestFlight",
            "Join the Example beta on TestFlight",
            "TestFlight This beta is full.",
            "Join the Example beta on TestFlight",
        ]
        for expected in (1, 1, 1, 2):
            monitor.run_once(self.cfg)
            self.assertEqual(send.call_count, expected)
        self.assertTrue(monitor.load_state()["available"])

    @patch.object(monitor, "send_telegram")
    @patch.object(monitor, "fetch", return_value="Join the Example beta on TestFlight")
    def test_failed_notification_retries_without_logging_token(self, fetch, send):
        send.side_effect = [
            requests.HTTPError("401 for https://api.telegram.org/bottest-token/sendMessage"),
            None,
        ]
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            monitor.run_once(self.cfg)
        self.assertNotIn(self.cfg["tg_token"], stderr.getvalue())
        self.assertIn("Telegram send failed", stderr.getvalue())
        self.assertEqual(monitor.load_state(), {})
        monitor.run_once(self.cfg)
        self.assertEqual(send.call_count, 2)
        self.assertTrue(monitor.load_state()["available"])

    @patch.object(monitor, "send_telegram")
    @patch.object(monitor, "fetch", side_effect=requests.Timeout("timed out"))
    def test_fetch_failure_preserves_state(self, fetch, send):
        monitor.save_state({"available": True})
        with contextlib.redirect_stderr(io.StringIO()):
            monitor.run_once(self.cfg)
        self.assertEqual(monitor.load_state(), {"available": True})
        send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
