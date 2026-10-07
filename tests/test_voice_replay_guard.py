import json
import tempfile
import unittest
from pathlib import Path

from backend.audio.replay_guard import VoiceReplayGuard


class VoiceReplayGuardTests(unittest.TestCase):
    def make_guard(self, path, wall, uptime, **overrides):
        options = {
            "startup_grace_seconds": 60,
            "startup_history_seconds": 300,
            "continuous_duplicate_seconds": 90,
            "explicit_duplicate_seconds": 8,
            "history_ttl_seconds": 3600,
            **overrides,
        }
        return VoiceReplayGuard(
            path,
            wall_clock=lambda: wall[0],
            uptime_clock=lambda: uptime[0],
            **options,
        )

    def test_continuous_audio_needs_explicit_session_activation(self):
        with tempfile.TemporaryDirectory() as folder:
            wall, uptime = [1000.0], [10.0]
            guard = self.make_guard(Path(folder) / "guard.json", wall, uptime)

            allowed, reason = guard.allow(
                "Chrome kholo", explicit_wake=False
            )
            self.assertFalse(allowed)
            self.assertEqual(reason, "session_not_armed")

            wall[0] += 120
            uptime[0] += 120
            allowed, reason = guard.allow(
                "Chrome kholo", explicit_wake=False
            )
            self.assertFalse(allowed)
            self.assertEqual(reason, "session_not_armed")

            guard.arm_continuous_session()
            allowed, reason = guard.allow(
                "Chrome kholo", explicit_wake=False
            )
            self.assertTrue(allowed)
            self.assertEqual(reason, "accepted")

    def test_explicit_wake_command_works_during_startup(self):
        with tempfile.TemporaryDirectory() as folder:
            wall, uptime = [1000.0], [10.0]
            guard = self.make_guard(Path(folder) / "guard.json", wall, uptime)

            allowed, reason = guard.allow(
                "Chrome kholo", explicit_wake=True
            )
            self.assertTrue(allowed)
            self.assertEqual(reason, "accepted")

    def test_duplicate_continuous_command_is_suppressed(self):
        with tempfile.TemporaryDirectory() as folder:
            wall, uptime = [1000.0], [100.0]
            guard = self.make_guard(
                Path(folder) / "guard.json",
                wall,
                uptime,
                startup_grace_seconds=0,
                startup_history_seconds=0,
            )
            guard.arm_continuous_session()
            self.assertTrue(guard.allow("Music chalao", explicit_wake=False)[0])
            wall[0] += 30
            uptime[0] += 30
            allowed, reason = guard.allow(
                "music chalao", explicit_wake=False
            )
            self.assertFalse(allowed)
            self.assertEqual(reason, "duplicate")

    def test_recent_history_blocks_replay_after_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "guard.json"
            wall, uptime = [1000.0], [100.0]
            first = self.make_guard(
                path,
                wall,
                uptime,
                startup_grace_seconds=0,
                startup_history_seconds=0,
            )
            first.arm_continuous_session()
            self.assertTrue(first.allow("YouTube kholo", explicit_wake=False)[0])

            wall[0] += 120
            uptime[0] = 5.0
            restarted = self.make_guard(
                path,
                wall,
                uptime,
                startup_grace_seconds=0,
            )
            restarted.arm_continuous_session()
            allowed, reason = restarted.allow(
                "youtube kholo", explicit_wake=False
            )
            self.assertFalse(allowed)
            self.assertEqual(reason, "previous_session_replay")

            payload = path.read_text(encoding="utf-8")
            self.assertNotIn("youtube", payload.casefold())
            self.assertIsInstance(json.loads(payload)["history"], dict)


if __name__ == "__main__":
    unittest.main()
