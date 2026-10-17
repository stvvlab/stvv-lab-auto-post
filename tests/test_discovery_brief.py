import unittest
from datetime import datetime, timedelta, timezone
from discovery_brief import build, search_url

class DiscoveryTests(unittest.TestCase):
    def test_links_and_no_automatic_replies(self):
        history = {"publication_log": [{"key": "daily_test", "source": None}]}
        text = build(history, datetime(2026, 10, 18, tzinfo=timezone(timedelta(hours=9))))
        self.assertIn("https://x.com/search?q=", text)
        self.assertIn("出典なし：1件", text)
        self.assertIn("無差別返信", text)
        self.assertIn("角括弧", text)

    def test_query_encoding(self):
        self.assertIn("%20", search_url("STVV 日本人"))
