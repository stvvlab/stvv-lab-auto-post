import unittest

from source_ledger_audit import audit_sources


class AuditSourceLedgerTests(unittest.TestCase):
    def test_orphaned_source_is_never_marked_safe(self):
        result = audit_sources(
            {"news": ["https://stvv.jp/news/event/20261002_2/"], "publication_log": []},
            {"cards": []})
        self.assertEqual(result["status"], "needs_reconciliation")
        self.assertEqual(len(result["used_sources_without_publication_log"]), 1)
        self.assertFalse(result["safe_to_repost_orphaned_sources"])

    def test_logged_publication_is_not_orphaned(self):
        url = "https://stvv.jp/news/game/20261026_1/"
        result = audit_sources(
            {"news": [url], "publication_log": [{"source": url}]},
            {"cards": [{"status": "published", "reviewed": True}]})
        self.assertEqual(result["used_sources_without_publication_log"], [])
        self.assertEqual(result["ready_reviewed_cards"], 0)

    def test_ready_count_only(self):
        result = audit_sources(
            {"news": [], "publication_log": []},
            {"cards": [{"status": "ready", "reviewed": True},
                       {"status": "ready", "reviewed": False},
                       {"status": "published", "reviewed": True}]})
        self.assertEqual(result["ready_reviewed_cards"], 1)

    def test_bad_ledger_fails_closed(self):
        with self.assertRaises(ValueError):
            audit_sources({"news": []}, {"cards": []})


if __name__ == "__main__":
    unittest.main()
