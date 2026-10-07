import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, call, patch

from fastapi.testclient import TestClient

from backend.config import AkshSettings
from backend.remote import RemoteCommandServer
from backend.remote_desktop.manager import RemoteDesktopManager
from backend.remote_desktop.input import (
    RemoteInputController,
    normalize_input_event,
    normalize_presentation_command,
    normalize_presentation_focus,
)
from backend.remote_desktop.sessions import ScreenSessionStore


AUTH = {"Authorization": "Bearer test-pairing-token"}


class SessionStoreTests(unittest.TestCase):
    def test_session_expires_after_inactivity(self):
        now = [10.0]
        expired = []
        store = ScreenSessionStore(
            ttl_seconds=60,
            clock=lambda: now[0],
            on_expire=expired.extend,
        )
        session = store.create()
        self.assertEqual(store.require(session.token), session)
        now[0] += 61
        with self.assertRaises(KeyError):
            store.require(session.token)
        self.assertEqual(expired, [session])

    def test_deliberately_replaced_session_is_distinct_from_expiration(self):
        store = ScreenSessionStore()
        session = store.create()
        store.clear(remember_revoked=True)

        with self.assertRaises(PermissionError):
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

    def test_failed_peer_can_detach_without_revoking_https_session(self):
        store = ScreenSessionStore()
        session = store.create()
        failed_peer = object()
        replacement_peer = object()

        self.assertIsNone(store.attach_peer(session.token, failed_peer))
        self.assertTrue(store.detach_peer(session.token, failed_peer))
        self.assertEqual(store.require(session.token), session)
        self.assertIsNone(store.attach_peer(session.token, replacement_peer))
        self.assertFalse(store.detach_peer(session.token, failed_peer))
        self.assertIs(store.require(session.token).peer, replacement_peer)


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

    def test_presentation_commands_are_dedicated_and_whitelisted(self):
        self.assertEqual(normalize_presentation_command(" NEXT "), "next")
        with self.assertRaises(ValueError):
            normalize_presentation_command("win+r")

    def test_presentation_focus_requires_a_bounded_coordinate_pair(self):
        self.assertEqual(
            normalize_presentation_focus(0.75, 0.25),
            (0.75, 0.25),
        )
        self.assertIsNone(normalize_presentation_focus(None, None))
        for x, y in ((0.5, None), (None, 0.5), (-0.1, 0.5), (0.5, 1.1)):
            with self.subTest(x=x, y=y), self.assertRaises(ValueError):
                normalize_presentation_focus(x, y)

    def test_presentation_commands_map_to_safe_keys(self):
        keyboard = Mock()
        mappings = {
            "next": ("press", ("pagedown",)),
            "previous": ("press", ("pageup",)),
            "zoom_in": ("hotkey", ("win", "+")),
            "zoom_out": ("hotkey", ("win", "-")),
            "zoom_reset": ("hotkey", ("win", "esc")),
        }

        for command, (method, arguments) in mappings.items():
            with self.subTest(command=command):
                keyboard.reset_mock()
                RemoteInputController._execute(
                    keyboard,
                    {"action": "presentation", "command": command},
                )
                getattr(keyboard, method).assert_called_once_with(*arguments)

    def test_focused_zoom_moves_pointer_before_magnifier_shortcut(self):
        keyboard = Mock()
        with patch(
            "backend.remote_desktop.input._captured_monitor_bounds",
            return_value=(-1920, 0, 1920, 1080),
        ):
            RemoteInputController._execute(
                keyboard,
                {
                    "action": "presentation",
                    "command": "zoom_in",
                    "x": 0.75,
                    "y": 0.25,
                },
            )

        self.assertEqual(
            keyboard.method_calls,
            [
                call.moveTo(-480, 270, duration=0.01),
                call.hotkey("win", "+"),
            ],
        )

    def test_focused_zoom_avoids_pyautogui_fail_safe_corners(self):
        keyboard = Mock()
        with patch(
            "backend.remote_desktop.input._captured_monitor_bounds",
            return_value=(0, 0, 1920, 1080),
        ):
            RemoteInputController._execute(
                keyboard,
                {
                    "action": "presentation",
                    "command": "zoom_in",
                    "x": 0.0,
                    "y": 0.0,
                },
            )

        self.assertEqual(
            keyboard.method_calls,
            [
                call.moveTo(1, 1, duration=0.01),
                call.hotkey("win", "+"),
            ],
        )

    def test_presentation_focus_is_rejected_for_non_zoom_commands(self):
        controller = RemoteInputController()
        with self.assertRaisesRegex(ValueError, "only supported for zoom"):
            controller.submit_presentation("next", x=0.5, y=0.5)
        with self.assertRaisesRegex(ValueError, "Both presentation focus"):
            controller.submit_presentation("zoom_in", x=0.5)

    def test_revoking_a_session_discards_its_queued_commands(self):
        controller = RemoteInputController()
        controller._thread = Mock()
        controller.submit_presentation("next")
        stale = controller._events.get_nowait()
        controller._events.put_nowait(stale)

        controller.revoke()

        replacement = controller._events.get_nowait()
        self.assertEqual(replacement["action"], "release")
        self.assertGreater(replacement["_generation"], stale["_generation"])
        self.assertTrue(controller._events.empty())


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
        heartbeat = client.post(
            "/v1/screen/sessions/current/heartbeat",
            headers=screen_headers,
        )
        self.assertEqual(heartbeat.status_code, 200)
        self.assertTrue(heartbeat.json()["active"])
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

    def test_presentation_state_and_actions_are_session_protected(self):
        server = self.make_server()
        server.screen.input.submit_presentation = Mock()
        server.screen.input.magnifier_running = Mock(return_value=False)
        client = TestClient(server.app)
        session = client.post(
            "/v1/screen/sessions",
            headers=AUTH,
        ).json()["session_id"]
        headers = {**AUTH, "X-Aksh-Screen-Session": session}

        self.assertEqual(
            client.get("/v1/screen/presentation", headers=AUTH).status_code,
            401,
        )
        self.assertEqual(
            client.post(
                "/v1/screen/presentation/actions",
                headers=headers,
                json={"action": "next"},
            ).status_code,
            400,
        )

        enabled = client.post(
            "/v1/screen/presentation/actions",
            headers=headers,
            json={"action": "enable"},
        )
        self.assertEqual(enabled.status_code, 200)
        self.assertEqual(
            enabled.json(),
            {"enabled": True, "zoom": 1.0, "revision": 1},
        )
        zoomed = client.post(
            "/v1/screen/presentation/actions",
            headers=headers,
            json={"action": "zoom_in", "x": 0.8, "y": 0.2},
        )
        self.assertEqual(
            zoomed.json(),
            {"enabled": True, "zoom": 1.25, "revision": 2},
        )
        client.post(
            "/v1/screen/presentation/actions",
            headers=headers,
            json={"action": "previous"},
        )
        current = client.get("/v1/screen/presentation", headers=headers)
        self.assertEqual(current.json(), zoomed.json())
        self.assertEqual(current.headers["cache-control"], "no-store")
        self.assertEqual(
            server.screen.input.submit_presentation.call_args_list,
            [
                call("zoom_in", x=0.8, y=0.2),
                call("previous"),
            ],
        )

    def test_presentation_focus_payload_is_strictly_validated(self):
        server = self.make_server()
        server.screen.input.submit_presentation = Mock()
        client = TestClient(server.app)
        session = client.post(
            "/v1/screen/sessions",
            headers=AUTH,
        ).json()["session_id"]
        headers = {**AUTH, "X-Aksh-Screen-Session": session}
        client.post(
            "/v1/screen/presentation/actions",
            headers=headers,
            json={"action": "enable"},
        )

        out_of_range = client.post(
            "/v1/screen/presentation/actions",
            headers=headers,
            json={"action": "zoom_in", "x": 1.01, "y": 0.5},
        )
        incomplete = client.post(
            "/v1/screen/presentation/actions",
            headers=headers,
            json={"action": "zoom_in", "x": 0.5},
        )
        non_zoom = client.post(
            "/v1/screen/presentation/actions",
            headers=headers,
            json={"action": "next", "x": 0.5, "y": 0.5},
        )

        self.assertEqual(out_of_range.status_code, 422)
        self.assertEqual(incomplete.status_code, 400)
        self.assertEqual(non_zoom.status_code, 400)
        server.screen.input.submit_presentation.assert_not_called()

    def test_replaced_phone_session_cannot_auto_renew_or_control(self):
        server = self.make_server()
        client = TestClient(server.app)
        first = client.post("/v1/screen/sessions", headers=AUTH).json()[
            "session_id"
        ]
        second = client.post("/v1/screen/sessions", headers=AUTH).json()[
            "session_id"
        ]

        first_headers = {**AUTH, "X-Aksh-Screen-Session": first}
        second_headers = {**AUTH, "X-Aksh-Screen-Session": second}
        self.assertEqual(
            client.get("/v1/screen/presentation", headers=first_headers).status_code,
            403,
        )
        self.assertEqual(
            client.get("/v1/screen/presentation", headers=second_headers).status_code,
            200,
        )

    def test_session_races_are_mapped_to_auth_errors(self):
        server = self.make_server()
        client = TestClient(server.app)
        session = client.post("/v1/screen/sessions", headers=AUTH).json()[
            "session_id"
        ]
        headers = {**AUTH, "X-Aksh-Screen-Session": session}

        server.screen.presentation_state = Mock(side_effect=KeyError("expired"))
        self.assertEqual(
            client.get("/v1/screen/presentation", headers=headers).status_code,
            401,
        )
        server.screen.submit_presentation_action = Mock(
            side_effect=PermissionError("replaced")
        )
        self.assertEqual(
            client.post(
                "/v1/screen/presentation/actions",
                headers=headers,
                json={"action": "enable"},
            ).status_code,
            403,
        )


class PresentationManagerTests(unittest.TestCase):
    def make_manager(self):
        manager = RemoteDesktopManager(
            AkshSettings(remote_screen_enabled=True)
        )
        manager.input = Mock()
        manager.input.magnifier_running.return_value = False
        session = manager.create_session()["session_id"]
        return manager, str(session)

    def test_zoom_is_bounded_and_reset_is_synchronized(self):
        manager, session = self.make_manager()
        manager.submit_presentation_action(session, "enable")
        for _ in range(20):
            state = manager.submit_presentation_action(session, "zoom_in")

        self.assertEqual(state["zoom"], 4.0)
        self.assertEqual(state["revision"], 13)
        self.assertEqual(
            manager.input.submit_presentation.call_count,
            12,
        )

        reset = manager.submit_presentation_action(session, "zoom_reset")
        self.assertEqual(
            reset,
            {"enabled": True, "zoom": 1.0, "revision": 14},
        )
        manager.disable_all()
        self.assertEqual(
            manager.presentation_snapshot(),
            {"enabled": False, "zoom": 1.0, "revision": 15},
        )
        self.assertEqual(
            manager.input.submit_presentation.call_args_list[-2:],
            [
                call("zoom_in"),
                call("zoom_reset"),
            ],
        )

    def test_concurrent_session_creation_keeps_one_authoritative_phone(self):
        manager = RemoteDesktopManager(
            AkshSettings(remote_screen_enabled=True)
        )
        with ThreadPoolExecutor(max_workers=4) as executor:
            sessions = list(
                executor.map(lambda _: manager.create_session(), range(4))
            )

        valid = 0
        replaced = 0
        for item in sessions:
            try:
                manager.require_session(str(item["session_id"]))
                valid += 1
            except PermissionError:
                replaced += 1
        self.assertEqual((valid, replaced), (1, 3))
        self.assertEqual(manager.sessions.active_count(), 1)
        manager.close()

    def test_replacing_phone_session_resets_presentation_and_magnifier(self):
        manager, first_session = self.make_manager()
        manager.submit_presentation_action(first_session, "enable")
        second_session = str(manager.create_session()["session_id"])

        with self.assertRaises(PermissionError):
            manager.presentation_state(first_session)
        self.assertEqual(
            manager.presentation_state(second_session),
            {"enabled": False, "zoom": 1.0, "revision": 2},
        )
        manager.input.submit_presentation.assert_not_called()

        manager.submit_presentation_action(second_session, "enable")
        manager.submit_presentation_action(second_session, "zoom_in")
        third_session = str(manager.create_session()["session_id"])
        self.assertEqual(
            manager.presentation_state(third_session),
            {"enabled": False, "zoom": 1.0, "revision": 5},
        )
        self.assertEqual(
            manager.input.submit_presentation.call_args_list,
            [call("zoom_in"), call("zoom_reset")],
        )

    def test_removing_owner_cleans_up_but_inactive_session_does_not(self):
        manager, session = self.make_manager()
        manager.remove_session(session)
        manager.input.submit_presentation.assert_not_called()

        replacement = str(manager.create_session()["session_id"])
        manager.submit_presentation_action(replacement, "enable")
        manager.submit_presentation_action(replacement, "zoom_in")
        manager.remove_session(replacement)

        self.assertEqual(
            manager.presentation_snapshot(),
            {"enabled": False, "zoom": 1.0, "revision": 3},
        )
        manager.input.submit_presentation.assert_has_calls(
            [call("zoom_in"), call("zoom_reset")]
        )

    def test_disable_and_close_only_reset_when_presentation_is_active(self):
        manager, session = self.make_manager()
        manager.disable_all()
        manager.close()
        manager.input.submit_presentation.assert_not_called()

        session = str(manager.create_session()["session_id"])
        manager.submit_presentation_action(session, "enable")
        manager.submit_presentation_action(session, "zoom_reset")
        manager.close()
        manager.input.submit_presentation.assert_not_called()
        self.assertEqual(
            manager.presentation_snapshot(),
            {"enabled": False, "zoom": 1.0, "revision": 2},
        )

        manager.input.submit_presentation.reset_mock()
        session = str(manager.create_session()["session_id"])
        manager.submit_presentation_action(session, "enable")
        manager.submit_presentation_action(session, "zoom_in")
        manager.close()
        self.assertEqual(
            manager.input.submit_presentation.call_args_list,
            [call("zoom_in"), call("zoom_reset")],
        )
        self.assertEqual(
            manager.presentation_snapshot(),
            {"enabled": False, "zoom": 1.0, "revision": 5},
        )

    def test_disable_all_closes_only_aksh_owned_magnifier(self):
        manager, session = self.make_manager()
        manager.submit_presentation_action(session, "enable")
        manager.disable_all()
        manager.input.submit_presentation.assert_not_called()

        session = str(manager.create_session()["session_id"])
        manager.submit_presentation_action(session, "enable")
        manager.submit_presentation_action(session, "zoom_in")
        manager.input.submit_presentation.reset_mock()
        manager.disable_all()
        manager.disable_all()

        manager.input.submit_presentation.assert_called_once_with("zoom_reset")
        self.assertEqual(
            manager.presentation_snapshot(),
            {"enabled": False, "zoom": 1.0, "revision": 5},
        )

    def test_preexisting_magnifier_is_restored_without_being_closed(self):
        manager, session = self.make_manager()
        manager.input.magnifier_running.return_value = True
        manager.submit_presentation_action(session, "enable")
        manager.submit_presentation_action(session, "zoom_in")
        manager.submit_presentation_action(session, "zoom_in")

        manager.disable_all()

        self.assertEqual(
            manager.input.submit_presentation.call_args_list,
            [
                call("zoom_in"),
                call("zoom_in"),
                call("zoom_out"),
                call("zoom_out"),
            ],
        )

    def test_expiration_closes_owned_presentation_state(self):
        manager, _ = self.make_manager()
        now = [10.0]
        manager.sessions.clock = lambda: now[0]
        manager.sessions.ttl_seconds = 60
        session = str(manager.create_session()["session_id"])
        manager.submit_presentation_action(session, "enable")
        manager.submit_presentation_action(session, "zoom_in")

        now[0] += 61
        self.assertEqual(manager.sessions.active_count(), 0)

        self.assertEqual(
            manager.presentation_snapshot(),
            {"enabled": False, "zoom": 1.0, "revision": 3},
        )
        manager.input.submit_presentation.assert_has_calls(
            [call("zoom_in"), call("zoom_reset")]
        )

    def test_presentation_expiry_is_checked_without_an_owner_request(self):
        now = [10.0]
        with patch("backend.remote_desktop.manager.threading.Timer") as timer_type:
            manager = RemoteDesktopManager(
                AkshSettings(remote_screen_enabled=True)
            )
            manager.sessions.clock = lambda: now[0]
            manager.sessions.ttl_seconds = 60
            manager.input = Mock()
            manager.input.magnifier_running.return_value = False
            session = str(manager.create_session()["session_id"])
            manager.submit_presentation_action(session, "enable")
            manager.submit_presentation_action(session, "zoom_in")

            timer_type.assert_called_once_with(
                15.0,
                manager._check_presentation_expiry,
            )
            timer_type.return_value.start.assert_called_once_with()
            now[0] += 61
            timer_type.call_args.args[1]()

        self.assertEqual(
            manager.presentation_snapshot(),
            {"enabled": False, "zoom": 1.0, "revision": 3},
        )
        manager.input.submit_presentation.assert_has_calls(
            [call("zoom_in"), call("zoom_reset")]
        )


class RemotePeerLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_offer_closes_peer_without_revoking_session(self):
        class FailingPeer:
            connectionState = "new"

            def __init__(self):
                self.closed = False

            def addTrack(self, _track):
                return None

            def on(self, _event):
                return lambda handler: handler

            async def setRemoteDescription(self, _description):
                raise RuntimeError("invalid offer")

            async def close(self):
                self.closed = True
                self.connectionState = "closed"

        manager = RemoteDesktopManager(
            AkshSettings(remote_screen_enabled=True)
        )
        session_id = manager.create_session()["session_id"]
        peer = FailingPeer()

        with patch(
            "backend.remote_desktop.manager.RTCPeerConnection",
            return_value=peer,
        ):
            with self.assertRaisesRegex(RuntimeError, "invalid offer"):
                await manager.accept_offer(
                    str(session_id),
                    sdp="v=0\r\n" * 10,
                    description_type="offer",
                )

        self.assertTrue(peer.closed)
        self.assertIsNone(manager.require_session(str(session_id)).peer)
        manager.close()


if __name__ == "__main__":
    unittest.main()
