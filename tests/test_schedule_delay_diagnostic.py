"""The scheduled workflow must report lateness without claiming a root cause."""
import unittest
from delivery_run import schedule_delay_diagnostic

class ScheduleDelayDiagnosticTests(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(schedule_delay_diagnostic(60), 'within_15_minutes')
    def test_moderate(self):
        self.assertEqual(schedule_delay_diagnostic(901), 'schedule_to_delivery_delay_unattributed')
    def test_severe_oct29_reproduction(self):
        self.assertEqual(schedule_delay_diagnostic(21362), 'severe_schedule_to_delivery_delay_unattributed')
    def test_clock_mismatch(self):
        self.assertEqual(schedule_delay_diagnostic(-1), 'clock_or_schedule_mismatch')

if __name__ == '__main__':
    unittest.main()
