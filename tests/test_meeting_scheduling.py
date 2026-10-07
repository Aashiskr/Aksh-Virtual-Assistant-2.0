import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.brain.fallback import local_intent, priority_intent
from backend.calendar_browser import ChromeCalendarBrowser, MeetingDraft
from backend.calendar_meetings import MeetingStore
from backend.chrome_accounts import (
    ChromeAccount,
    ChromeAccountResolver,
    MeetingSchedulingError,
)
from backend.remote.jobs import RemoteJobStore


class MeetingIntentTests(unittest.TestCase):
    def test_explicit_account_is_preserved(self):
        response = priority_intent(
            "schedule a meeting with dezignbank account at 10 am"
        )
        self.assertIsNotNone(response)
        action = response.actions[0]
        self.assertEqual(action.name, "schedule_meeting")
        self.assertEqual(action.parameters["account"], "dezignbank")
        self.assertEqual(action.parameters["time"], "10 am")

    def test_missing_account_is_left_out_for_any_account_fallback(self):
        response = local_intent("schedule meeting at 10 am")
        action = response.actions[0]
        self.assertEqual(action.name, "schedule_meeting")
        self.assertNotIn("account", action.parameters)

    def test_missing_time_requests_clarification(self):
        response = priority_intent("dezignbank account se meeting banao")
        self.assertTrue(response.needs_clarification)
        self.assertEqual(response.actions, [])


class ChromeAccountResolverTests(unittest.TestCase):
    def write_profile_data(self, root: Path) -> None:
        (root / "Default").mkdir(parents=True)
        (root / "Profile 2").mkdir(parents=True)
        (root / "Local State").write_text(
            json.dumps(
                {
                    "profile": {
                        "info_cache": {
                            "Default": {
                                "name": "Aksh",
                                "gaia_name": "Aksh",
                                "user_name": "aksh@example.com",
                            },
                            "Profile 2": {
                                "name": "dezignbank",
                                "gaia_name": "DezignBank",
                                "user_name": "hello@dezignbank.com",
                            },
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        (root / "Default" / "Preferences").write_text(
            json.dumps(
                {
                    "account_info": [
                        {
                            "email": "aksh@example.com",
                            "full_name": "Aksh",
                        },
                        {
                            "email": "secondary@example.com",
                            "full_name": "Secondary Work",
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )

    def test_resolves_named_profile_and_secondary_account(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.write_profile_data(root)
            resolver = ChromeAccountResolver(root)
            named = resolver.resolve("dezignbank")
            self.assertEqual(named.profile_directory, "Profile 2")
            self.assertEqual(named.email, "hello@dezignbank.com")
            secondary = resolver.resolve("Secondary Work")
            self.assertEqual(secondary.profile_directory, "Default")
            self.assertEqual(secondary.email, "secondary@example.com")

    def test_explicit_missing_account_never_falls_back(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.write_profile_data(root)
            with self.assertRaises(MeetingSchedulingError) as raised:
                ChromeAccountResolver(root).resolve("missing account")
            self.assertIn("doosre account se nahi", str(raised.exception))

    def test_no_requested_account_uses_an_available_primary(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.write_profile_data(root)
            account = ChromeAccountResolver(root).resolve()
            self.assertTrue(account.primary)


class CalendarTemplateTests(unittest.TestCase):
    def test_template_targets_profile_account_time_and_guests(self):
        account = ChromeAccount(
            "Profile 2",
            "dezignbank",
            "DezignBank",
            "hello@dezignbank.com",
        )
        start = datetime(2026, 9, 2, 10, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
        url = ChromeCalendarBrowser.event_url(
            account,
            MeetingDraft(
                "Design review",
                start,
                start + timedelta(minutes=30),
                ("guest@example.com",),
            ),
        )
        self.assertIn("authuser=hello%40dezignbank.com", url)
        self.assertIn("dates=20260902T043000Z%2F20260902T050000Z", url)
        self.assertIn("add=guest%40example.com", url)


class MeetingPersistenceTests(unittest.TestCase):
    def test_meeting_is_saved_and_exposed_on_remote_job(self):
        meeting = {
            "id": "meeting-1",
            "time": "10 am",
            "link": "https://meet.google.com/abc-defg-hij",
        }
        with tempfile.TemporaryDirectory() as folder:
            store = MeetingStore(Path(folder) / "meetings.json")
            store.append(meeting)
            self.assertEqual(store.latest_id(), "meeting-1")

        jobs = RemoteJobStore()
        job = jobs.create()
        jobs.complete(job.id, "confirm", "done", meeting=meeting)
        self.assertEqual(jobs.get(job.id).public()["meeting"]["id"], "meeting-1")


if __name__ == "__main__":
    unittest.main()
