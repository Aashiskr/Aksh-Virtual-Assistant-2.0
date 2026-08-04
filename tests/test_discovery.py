import unittest
from unittest.mock import Mock, patch

from backend.config import AkshSettings
from backend.remote.discovery import DiscoveryPublisher, device_id_for_token


class DiscoveryTests(unittest.TestCase):
    def test_device_id_is_stable_and_does_not_expose_token(self):
        token = "a-secret-pairing-token-with-enough-entropy"
        first = device_id_for_token(token)
        self.assertEqual(first, device_id_for_token(token))
        self.assertEqual(len(first), 24)
        self.assertNotIn(token, first)

    @patch("backend.remote.discovery.requests.put")
    def test_publisher_authenticates_and_sends_only_public_url(self, put):
        put.return_value = Mock(raise_for_status=Mock())
        settings = AkshSettings(
            remote_discovery_url="https://relay.example.test"
        )
        publisher = DiscoveryPublisher(settings, "private-pairing-token-value")
        publisher.publish("https://current-tunnel.example.test")
        _, kwargs = put.call_args
        self.assertEqual(
            kwargs["json"], {"url": "https://current-tunnel.example.test"}
        )
        self.assertNotIn("private-pairing-token-value", str(kwargs["json"]))
        self.assertTrue(
            kwargs["headers"]["Authorization"].startswith("Bearer ")
        )


if __name__ == "__main__":
    unittest.main()
