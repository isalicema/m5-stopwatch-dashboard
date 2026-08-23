import unittest
from unittest import mock

from bridge.discovery import (
    COMPLETION_EVENT_PREFIX,
    CompletionBeacon,
    DISCOVERY_QUERY,
    DISCOVERY_RESPONSE_PREFIX,
    build_discovery_response,
    build_completion_event,
)


class DiscoveryTests(unittest.TestCase):
    def test_protocol_constants_are_ascii_and_versioned(self):
        self.assertEqual(DISCOVERY_QUERY, b"M5DASH_DISCOVER_V1")
        self.assertEqual(DISCOVERY_RESPONSE_PREFIX, "M5DASH_BRIDGE_V1")

    def test_response_contains_http_port_only(self):
        self.assertEqual(build_discovery_response(8765), b"M5DASH_BRIDGE_V1|8765")

    def test_rejects_invalid_port(self):
        with self.assertRaises(ValueError):
            build_discovery_response(0)

    def test_completion_beacon_contains_no_token_or_task_content(self):
        self.assertEqual(COMPLETION_EVENT_PREFIX, "M5DASH_EVENT_V1|completion|")
        self.assertEqual(build_completion_event("codex"), b"M5DASH_EVENT_V1|completion|codex")
        with self.assertRaises(ValueError):
            build_completion_event("unknown")

    def test_beacon_targets_only_recent_authenticated_clients(self):
        beacon = CompletionBeacon(port=42101)
        beacon.note_client("127.0.0.1")
        beacon.note_client("192.168.1.20")
        sock = mock.MagicMock()
        with mock.patch("bridge.discovery.socket.socket", return_value=sock):
            sent = beacon.notify("claude")
        self.assertEqual(sent, 1)
        sock.sendto.assert_called_once_with(
            b"M5DASH_EVENT_V1|completion|claude", ("192.168.1.20", 42101)
        )


if __name__ == "__main__":
    unittest.main()
