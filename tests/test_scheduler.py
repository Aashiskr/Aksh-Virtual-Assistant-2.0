import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.scheduler import ReminderScheduler, parse_when


class SchedulerTests(unittest.TestCase):
    def test_time_in_past_moves_to_next_day(self):
        now = datetime(2026, 7, 27, 20, 0, tzinfo=timezone.utc)
        parsed = parse_when("7:30 PM", now)
        self.assertEqual(parsed.date(), (now + timedelta(days=1)).date())
        self.assertEqual((parsed.hour, parsed.minute), (19, 30))

    def test_tomorrow_hinglish_time(self):
        now = datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc)
        parsed = parse_when("kal 8 am", now)
        self.assertEqual(parsed.date(), (now + timedelta(days=1)).date())
        self.assertEqual(parsed.hour, 8)

    def test_scheduler_persists_pending_item(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "schedule.json"
            scheduler = ReminderScheduler(path, on_due=lambda item: None)
            item = scheduler.add(
                kind="reminder", when="11:59 PM", message="test reminder"
            )
            self.assertTrue(path.exists())
            self.assertEqual(scheduler.pending()[0]["id"], item["id"])


if __name__ == "__main__":
    unittest.main()
