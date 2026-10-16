"""Offline tests: never contact Buffer or publish to X."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
import auto_feedback as a

NOW = datetime(2026, 10, 16, 3, 0, tzinfo=a.JST)

def entry(i, views=100, reactions=5, updated=True):
    return {
        "post_key": f"k-{i}", "slot": "news",
        "submitted_at": (NOW - timedelta(days=3)).isoformat(),
        "checked_at": NOW.isoformat(),
        "status": "sent",
        "metrics_updated_at": NOW.isoformat() if updated else None,
        "values": {"impressions": views, "reactions": reactions, "comments": 0},
    }

class FakeResponse:
    def raise_for_status(self):
        return None
    def json(self):
        return {"data": {"post": {"id": "test-id", "status": "sent", "metricsUpdatedAt": NOW.isoformat(), "metrics": [
            {"type": "impressions", "value": "100", "unit": "count"},
            {"type": "reactions", "value": 5, "unit": "count"}
        ]}}}

class FakeSession:
    def __init__(self):
        self.payload = None
    def post(self, *args, **kwargs):
        self.payload = kwargs
        return FakeResponse()

class FeedbackTests(unittest.TestCase):
    def test_query_follows_official_shape(self):
        client = FakeSession()
        result = a.metric_query("test-id", client, "secret")
        self.assertEqual(result["id"], "test-id")
        self.assertIn('post(input: { id: "test-id" })', client.payload["json"]["query"])
        self.assertIn("metricsUpdatedAt", client.payload["json"]["query"])
    def test_unavailable_metrics_not_scored(self):
        self.assertIsNone(a.engagement_rate(entry(1, updated=False)))
        self.assertIsNone(a.engagement_rate(entry(1, views=10)))
        no_reactions = entry(1)
        no_reactions["values"] = {"impressions": 500}
        self.assertIsNone(a.engagement_rate(no_reactions))
    def test_zero_reactions_is_valid_if_measured(self):
        self.assertEqual(a.engagement_rate(entry(1, reactions=0)), 0)
    def test_no_ratings_under_minimum_sample(self):
        self.assertEqual(a.automatic_ratings({"metrics": [entry(i) for i in range(9)]}, NOW), [])
    def test_ratings_with_ten_comparable_posts(self):
        reviews = a.automatic_ratings({"metrics": [entry(i, reactions=i) for i in range(10)]}, NOW)
        self.assertEqual(len(reviews), 10)
        self.assertEqual(reviews[0]["rating"], 1)
        self.assertEqual(reviews[-1]["rating"], 5)
    def test_metric_units_and_nonnumeric_ignored(self):
        result = a.unpack_metrics({"metrics": [
            {"type": "impressions", "value": 120, "unit": "count"},
            {"type": "engagementRate", "value": 3.1, "unit": "percentage"},
            {"type": "comments", "value": "-5", "unit": "count"},
            {"type": "reactions", "value": "none", "unit": "count"},
        ]})
        self.assertEqual(result, {"impressions": 120.0, "engagementRate": 3.1})
    def test_disabled_collection_preserves_manual_feedback(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fb = root / "feedback.json"
            hist = root / "posted.json"
            fb.write_text(json.dumps({"settings": {"feedback_enabled": True, "auto_metrics_enabled": False, "auto_improvement_enabled": False, "weekly_report_enabled": False}, "feedback": [{"post_key": "k-1", "rating": 2}]}))
            hist.write_text(json.dumps({"publication_log": []}))
            with patch.object(a, "FEEDBACK", fb), patch.object(a, "HISTORY", hist):
                a.run(now=NOW)
            updated = json.loads(fb.read_text())
            self.assertEqual(updated["feedback"], [{"post_key": "k-1", "rating": 2}])
            self.assertEqual(updated.get("metrics"), None)

if __name__ == "__main__":
    unittest.main()
