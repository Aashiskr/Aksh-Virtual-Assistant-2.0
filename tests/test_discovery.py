import unittest
from unittest.mock import Mock, patch

from backend.config import AkshSettings
from backend.remote.discovery import DiscoveryPublisher, device_id_for_token
from backend.remote.tunnel import RemoteTunnel


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


class RemoteTunnelRecoveryTests(unittest.TestCase):
    @patch("backend.remote.tunnel.threading.Timer")
    def test_exited_quick_tunnel_clears_stale_url_and_restarts(self, timer):
        tunnel = RemoteTunnel(AkshSettings(remote_tunnel_enabled=True))
        process = Mock()
        process.wait.return_value = 1
        tunnel._process = process
        tunnel.public_url = "https://expired-link.trycloudflare.com"
        tunnel._ready.set()

        tunnel._watch_process(process)

        self.assertEqual(tunnel.public_url, "")
        self.assertEqual(tunnel.status, "disconnected")
        timer.assert_called_once_with(2.0, tunnel.start)
        timer.return_value.start.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
