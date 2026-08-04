import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from backend.monitors.battery import BatteryMonitor


FULL_MESSAGE = "Battery is fully charged. You can unplug the charger."


class BatteryMonitorTests(unittest.TestCase):
    def test_full_charge_warns_at_most_twice_per_session(self):
        alerts = Mock()
        clock = Mock(return_value=1000.0)
        monitor = BatteryMonitor(
            alerts,
            full_warning_limit=2,
            full_warning_cooldown_seconds=1800,
            clock=clock,
        )
        monitor._check_plug_state(True)
        monitor._check_level(100, True)
        monitor._check_level(100, True)
        alerts.assert_called_once_with(FULL_MESSAGE)

        clock.return_value = 2800.0
        monitor._check_level(100, True)
        monitor._check_level(100, True)
        self.assertEqual(alerts.call_count, 2)

        clock.return_value = 10000.0
        monitor._check_level(100, True)
        self.assertEqual(alerts.call_count, 2)

    def test_unplug_and_replug_starts_a_new_warning_session(self):
        alerts = Mock()
        clock = Mock(return_value=1000.0)
        monitor = BatteryMonitor(
            alerts,
            full_warning_cooldown_seconds=0,
            clock=clock,
        )
        monitor._check_plug_state(True)
        monitor._check_level(100, True)
        monitor._check_level(100, True)
        monitor._check_plug_state(False)
        monitor._check_plug_state(True)
        monitor._check_level(100, True)
        full_alerts = [
            call
            for call in alerts.call_args_list
            if call.args == (FULL_MESSAGE,)
        ]
        self.assertEqual(len(full_alerts), 3)

    def test_warning_count_survives_aksh_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            state_path = Path(folder) / "battery.json"
            first_alerts = Mock()
            first_clock = Mock(return_value=1000.0)
            first = BatteryMonitor(
                first_alerts,
                state_path=state_path,
                full_warning_cooldown_seconds=1800,
                clock=first_clock,
            )
            first._check_plug_state(True)
            first._check_level(100, True)

            second_alerts = Mock()
            second_clock = Mock(return_value=1200.0)
            second = BatteryMonitor(
                second_alerts,
                state_path=state_path,
                full_warning_cooldown_seconds=1800,
                clock=second_clock,
            )
            second._check_plug_state(True)
            second._check_level(100, True)
            second_alerts.assert_not_called()

            second_clock.return_value = 2800.0
            second._check_level(100, True)
            second_alerts.assert_called_once_with(FULL_MESSAGE)


if __name__ == "__main__":
    unittest.main()
