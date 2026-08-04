import unittest

from fastapi.testclient import TestClient

from backend.config import AkshSettings
from backend.remote import RemoteCommandServer


class RemoteApiTests(unittest.TestCase):
    def make_server(self):
        settings = AkshSettings(
            remote_token="test-pairing-token",
            remote_enabled=True,
        )
        return RemoteCommandServer(settings, lambda text: f"done: {text}")

    def test_health_requires_pairing_token(self):
        server = self.make_server()
        client = TestClient(server.app)
        self.assertEqual(client.get("/v1/health").status_code, 401)
        response = client.get(
            "/v1/health",
            headers={"Authorization": "Bearer test-pairing-token"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_text_command_is_queued(self):
        server = self.make_server()
        client = TestClient(server.app)
        response = client.post(
            "/v1/commands/text",
            headers={"Authorization": "Bearer test-pairing-token"},
            json={"text": "battery kitni hai"},
        )
        self.assertEqual(response.status_code, 202)
        job_id, kind, text = server.pending.get_nowait()
        self.assertEqual(job_id, response.json()["job_id"])
        self.assertEqual((kind, text), ("text", "battery kitni hai"))


if __name__ == "__main__":
    unittest.main()
