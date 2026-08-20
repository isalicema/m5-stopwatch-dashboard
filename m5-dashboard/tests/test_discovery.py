import unittest

from bridge.discovery import (
    DISCOVERY_QUERY,
    DISCOVERY_RESPONSE_PREFIX,
    build_discovery_response,
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


if __name__ == "__main__":
    unittest.main()
