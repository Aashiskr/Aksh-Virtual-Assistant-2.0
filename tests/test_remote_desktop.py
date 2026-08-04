import unittest
from unittest.mock import Mock

from fastapi.testclient import TestClient

from backend.config import AkshSettings
from backend.remote import RemoteCommandServer
from backend.remote_desktop.input import normalize_input_event
from backend.remote_desktop.sessions import ScreenSessionStore


AUTH = {"Authorization": "Bearer test-pairing-token"}


class SessionStoreTests(unittest.TestCase):
    def test_session_expires_after_inactivity(self):
        now = [10.0]
        store = ScreenSessionStore(ttl_seconds=60, clock=lambda: now[0])
        session = store.create()
        self.assertEqual(store.require(session.token), session)
        now[0] += 61
        with self.assertRaises(KeyError):
            store.require(session.token)

    def test_oldest_session_is_replaced_at_limit(self):
        now = [1.0]
        store = ScreenSessionStore(
            maximum_sessions=1,
            clock=lambda: now[0],
        )
        first = store.create()
        now[0] += 1
        second = store.create()
        with self.assertRaises(KeyError):
            store.require(first.token)
        self.assertEqual(store.require(second.token), second)


class RemoteInputValidationTests(unittest.TestCase):
    def test_pointer_and_scroll_are_bounded(self):
        self.assertEqual(
            normalize_input_event({"action": "click", "x": 0.25, "y": 0.8}),
            {"action": "click", "x": 0.25, "y": 0.8},
        )
        self.assertEqual(
            normalize_input_event({"action": "scroll", "delta": 99}),
            {"action": "scroll", "delta": 12},
        )
        with self.assertRaises(ValueError):
            normalize_input_event({"action": "click", "x": 2, "y": 0.5})

    def test_arbitrary_hotkeys_are_rejected(self):
        with self.assertRaises(ValueError):
            normalize_input_event({"action": "key", "key": "win+r"})
        self.assertEqual(
            normalize_input_event({"action": "key", "key": "alt_tab"}),
            {"action": "key", "key": "alt_tab"},
        )


class RemoteScreenApiTests(unittest.TestCase):
    def make_server(self, *, enabled=True):
        settings = AkshSettings(
            remote_token="test-pairing-token",
            remote_screen_enabled=enabled,
        )
        return RemoteCommandServer(settings, lambda text: text)

    def test_laptop_permission_is_required(self):
        client = TestClient(self.make_server(enabled=False).app)
        response = client.post("/v1/screen/sessions", headers=AUTH)
        self.assertEqual(response.status_code, 403)
        self.assertIn("Remote screen access enable", response.json()["detail"])

    def test_authenticated_session_protects_frames_and_input(self):
        server = self.make_server()
        server.screen.capture_frame = Mock(return_value=b"jpeg")
        server.screen.submit_input = Mock()
        client = TestClient(server.app)

        self.assertEqual(client.post("/v1/screen/sessions").status_code, 401)
        session_response = client.post("/v1/screen/sessions", headers=AUTH)
        self.assertEqual(session_response.status_code, 201)
        session = session_response.json()["session_id"]
        screen_headers = {**AUTH, "X-Aksh-Screen-Session": session}

        missing = client.get("/v1/screen/frame", headers=AUTH)
        self.assertEqual(missing.status_code, 401)
        frame = client.get("/v1/screen/frame", headers=screen_headers)
        self.assertEqual(frame.status_code, 200)
        self.assertEqual(frame.content, b"jpeg")
        response = client.post(
            "/v1/screen/input",
            headers=screen_headers,
            json={"action": "click", "x": 0.2, "y": 0.4},
        )
        self.assertEqual(response.status_code, 202)
        server.screen.submit_input.assert_called_once()

        closed = client.delete(
            "/v1/screen/sessions/current",
            headers=screen_headers,
        )
        self.assertEqual(closed.status_code, 204)
        self.assertEqual(
            client.get("/v1/screen/frame", headers=screen_headers).status_code,
            401,
        )


if __name__ == "__main__":
    unittest.main()
