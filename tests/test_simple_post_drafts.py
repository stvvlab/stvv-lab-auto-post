import unittest
from simple_post_drafts import build_drafts, draft_from_candidate


def item(**updates):
    result = {"status": "needs_editorial_review",
              "source_url": "https://stvv.jp/news/game/20261028_1/",
              "official_heading": "公式試合情報のお知らせ",
              "source_body": "公式情報を確認してください。" * 5,
              "date_jst": "2026-10-28"}
    result.update(updates)
    return result


class SimplePostDraftTests(unittest.TestCase):
    def test_official_game_heading_becomes_unapproved_draft(self):
        draft = draft_from_candidate(item())
        self.assertEqual(draft["status"], "needs_review_and_image")
        self.assertFalse(draft["reviewed"])
        self.assertIn("公式試合情報のお知らせ", draft["text"])

    def test_sponsors_are_not_published_as_news(self):
        self.assertIsNone(draft_from_candidate(item(
            source_url="https://stvv.jp/news/sponsor/20261028_1/")))

    def test_no_body_no_claim(self):
        self.assertIsNone(draft_from_candidate(item(source_body="")))

    def test_duplicate_source_produces_single_candidate(self):
        result = build_drafts({"candidates": [item(), item()]})
        self.assertEqual(len(result["drafts"]), 1)
        self.assertFalse(result["publication_performed"])
        self.assertFalse(result["image_generation_performed"])


if __name__ == "__main__":
    unittest.main()
