import unittest

from backend.config import AkshSettings, _secure_url_or_blank


class PublicConfigurationTests(unittest.TestCase):
    def test_remote_api_is_loopback_only_by_default(self):
        self.assertEqual(AkshSettings().remote_host, "127.0.0.1")

    def test_no_shared_discovery_relay_is_built_in(self):
        self.assertEqual(AkshSettings().remote_discovery_url, "")

    def test_remote_urls_must_be_https_without_embedded_credentials(self):
        self.assertEqual(
            _secure_url_or_blank("https://relay.example.test/"),
            "https://relay.example.test",
        )
        self.assertEqual(_secure_url_or_blank("http://relay.example.test"), "")
        self.assertEqual(
            _secure_url_or_blank("https://user:pass@relay.example.test"),
            "",
        )


if __name__ == "__main__":
    unittest.main()
