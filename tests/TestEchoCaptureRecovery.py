import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.echo_capture_recovery import CaptureRecoveryMonitor


class FakeDeviceManager:
    def __init__(self):
        self.hwnd_window = SimpleNamespace(hwnd=0, exists=False)
        self.executor = SimpleNamespace(paused=False)
        self.capture_method = SimpleNamespace(connected=lambda: False)
        self.starts = 0

    def start(self):
        self.starts += 1


class TestEchoCaptureRecovery(unittest.TestCase):
    def setUp(self):
        self.manager = FakeDeviceManager()
        self.exit_event = threading.Event()
        self.monitor = CaptureRecoveryMonitor(
            self.manager, self.exit_event, retry_delay=5,
        )

    def test_game_restart_reconnects_without_restart_of_host(self):
        self.manager.hwnd_window.hwnd = 100
        self.manager.hwnd_window.exists = True
        with patch("src.echo_capture_recovery.time.monotonic", return_value=10):
            self.assertTrue(self.monitor.poll())
            self.assertFalse(self.monitor.poll())
        self.assertEqual(1, self.manager.starts)

        self.manager.hwnd_window.exists = False
        self.assertFalse(self.monitor.poll())
        self.manager.hwnd_window.hwnd = 200
        self.manager.hwnd_window.exists = True
        with patch("src.echo_capture_recovery.time.monotonic", return_value=11):
            self.assertTrue(self.monitor.poll())
        self.assertEqual(2, self.manager.starts)

    def test_failed_reconnect_is_retried_but_not_on_every_poll(self):
        self.manager.hwnd_window.hwnd = 100
        self.manager.hwnd_window.exists = True
        with patch("src.echo_capture_recovery.time.monotonic", side_effect=[10, 12, 15]):
            self.assertTrue(self.monitor.poll())
            self.assertFalse(self.monitor.poll())
            self.assertTrue(self.monitor.poll())
        self.assertEqual(2, self.manager.starts)

    def test_only_active_disconnected_capture_is_restarted(self):
        self.manager.hwnd_window.hwnd = 100
        self.manager.hwnd_window.exists = True
        self.manager.executor.paused = True
        self.assertFalse(self.monitor.poll())
        self.manager.executor.paused = False
        self.manager.capture_method = None
        # A failed WGC/BitBlt startup may leave capture_method=None. It must
        # remain retryable while the user has screenshot capture enabled.
        self.assertTrue(self.monitor.poll())
        self.manager.capture_method = SimpleNamespace(connected=lambda: True)
        self.assertFalse(self.monitor.poll())
        self.assertEqual(1, self.manager.starts)

    def test_shutdown_stops_reconnect_checks(self):
        self.manager.hwnd_window.hwnd = 100
        self.manager.hwnd_window.exists = True
        self.exit_event.set()
        self.assertFalse(self.monitor.poll())
        self.assertEqual(0, self.manager.starts)


if __name__ == "__main__":
    unittest.main()
