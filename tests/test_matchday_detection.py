import unittest
from datetime import datetime, timezone
from unittest.mock import Mock
from matchday_detection import detect, scan

NOW = datetime(2026, 11, 2, tzinfo=timezone.utc)


class MatchdayDetectionTests(unittest.TestCase):
    def test_provisional_not_publishable(self):
        events = [{"idEvent": "123", "idHomeTeam": "135461",
                   "idAwayTeam": "999", "strAwayTeam": "OH Leuven",
                   "dateEvent": "2026-11-02"}]
        rows = detect(events, NOW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["opponent"], "OH Leuven")
        self.assertFalse(rows[0]["matchday_confirmed"])
        self.assertFalse(rows[0]["can_publish"])
        self.assertIsNone(rows[0]["kickoff_jst"])

    def test_unrelated_and_invalid_events_ignored(self):
        events = [{"idHomeTeam": "1", "idAwayTeam": "2",
                   "dateEvent": "2026-11-02", "strAwayTeam": "Other"},
                  {"idHomeTeam": "135461", "idAwayTeam": "3",
                   "dateEvent": "invalid", "strAwayTeam": "Other"},
                  None]
        self.assertEqual(detect(events, NOW), [])

    def test_unavailable_source_fails_closed(self):
        session = Mock()
        session.get.side_effect = TimeoutError()
        report = scan(NOW, session)
        self.assertEqual(report["status"], "provider_unavailable")
        self.assertFalse(report["can_publish"])
        self.assertEqual(report["candidates"], [])

    def test_bad_payload_fails_closed(self):
        session = Mock()
        session.get.return_value.json.return_value = {"events": None}
        report = scan(NOW, session)
        self.assertEqual(report["status"], "provider_unavailable")
        self.assertFalse(report["matchday_confirmed"])


if __name__ == "__main__":
    unittest.main()
