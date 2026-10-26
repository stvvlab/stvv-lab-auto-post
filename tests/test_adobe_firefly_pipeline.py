import unittest
from unittest.mock import Mock
from adobe_firefly_pipeline import prepare, generate, approved_status_url


class FireflyPipelineTests(unittest.TestCase):
    SOURCE = "https://stvv.jp/news/game/20261026_1/"

    def test_draft_not_publication_approval(self):
        brief = prepare(self.SOURCE, "Official " + self.SOURCE, {"publication_log": []})
        self.assertEqual("brief_only", brief["status"])
        self.assertEqual(4, len(__import__("design_brief").ART_DIRECTIONS))
        self.assertNotIn("abstract-motion", __import__("design_brief").ART_DIRECTIONS)

    def test_reject_untrusted_status_url(self):
        self.assertFalse(approved_status_url("https://example.com/v3/status/a"))
        self.assertFalse(approved_status_url("http://firefly-api.adobe.io/v3/status/a"))
        self.assertTrue(approved_status_url("https://firefly-api.adobe.io/v3/status/job"))

    def test_no_generation_without_valid_history(self):
        with self.assertRaises(ValueError):
            prepare(self.SOURCE, "Official " + self.SOURCE, {})

    def test_mocked_adobe_success(self):
        session = Mock()
        token = Mock()
        token.json.return_value = {"access_token": "test-token"}
        start = Mock()
        start.json.return_value = {"outputs": [{"image": {"url": "https://example.com/image.png"}}]}
        session.post.side_effect = [token, start]
        self.assertEqual("https://example.com/image.png",
                         generate(session, "football", "id", "secret"))
        self.assertEqual(2, session.post.call_count)


if __name__ == "__main__":
    unittest.main()
