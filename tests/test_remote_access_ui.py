import unittest

from frontend.desktop.remote_access_ui import phone_setup_values


class PhoneSetupValuesTests(unittest.TestCase):
    def test_returns_the_four_android_setup_values(self):
        info = {
            "discovery_url": " https://relay.example.test/ ",
            "device_id": "device-123",
            "token": "private-token",
            "public_url": "https://laptop.trycloudflare.com",
            "local_url": "http://127.0.0.1:8765",
        }

        self.assertEqual(
            phone_setup_values(info),
            {
                "discovery_url": "https://relay.example.test/",
                "device_id": "device-123",
                "token": "private-token",
                "manual_url": "https://laptop.trycloudflare.com",
            },
        )

    def test_missing_optional_urls_are_blank(self):
        self.assertEqual(
            phone_setup_values({"device_id": "device", "token": "token"}),
            {
                "discovery_url": "",
                "device_id": "device",
                "token": "token",
                "manual_url": "",
            },
        )


if __name__ == "__main__":
    unittest.main()
