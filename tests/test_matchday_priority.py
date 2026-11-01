"""Offline tests: match-day priority never bypasses review or due-time gates."""
import unittest
from datetime import datetime

from matchday_priority import is_matchday_card, prioritize


DUE = datetime.fromisoformat("2026-11-02T18:00:00+09:00")


def card(phase="matchday", **overrides):
    data = {
        "reviewed": True, "status": "ready",
        "editorial_purpose": {"kind": "fixture", "phase": phase,
                              "event_id": "stvv-fixture-2026-11-02"},
        "publish_due_jst": DUE.isoformat(),
    }
    data.update(overrides)
    return data


class MatchdayPriorityTests(unittest.TestCase):
    def test_exact_reviewed_matchday_goes_first_without_changing_candidates(self):
        items = [("normal", "https://stvv.jp/news/a"),
                 ("matchday", "https://stvv.jp/news/b")]
        cards = {"normal": {"reviewed": True, "status": "ready"},
                 "matchday": card()}
        result = prioritize(items, "news", DUE, lambda slot, text, source: cards[text])
        self.assertEqual(result, list(reversed(items)))
        self.assertEqual(len(result), len(items))

    def test_no_matchday_card_preserves_order(self):
        items = [("one", "a"), ("two", "b")]
        self.assertEqual(prioritize(items, "news", DUE,
                                   lambda slot, text, source: None), items)

    def test_no_unreviewed_stale_or_wrong_phase_priority(self):
        invalid = [
            card(reviewed=False),
            card(status="draft"),
            card(publish_due_jst="2026-11-03T18:00:00+09:00"),
            card(phase="initial"),
            card(editorial_purpose={"kind": "fixture", "phase": "matchday"}),
            card(editorial_purpose={"kind": "fixture", "phase": "unknown",
                                    "event_id": "fixture"}),
        ]
        for item in invalid:
            with self.subTest(item=item):
                self.assertFalse(is_matchday_card(item, DUE))

    def test_lineup_and_final_only_if_explicitly_reviewed(self):
        for kind, phase in (("fixture", "lineup"), ("match", "lineup"),
                            ("match", "final"), ("result", "recap")):
            with self.subTest(kind=kind, phase=phase):
                item = card(editorial_purpose={"kind": kind, "phase": phase,
                                               "event_id": "fixture"})
                self.assertTrue(is_matchday_card(item, DUE))


if __name__ == "__main__":
    unittest.main()
