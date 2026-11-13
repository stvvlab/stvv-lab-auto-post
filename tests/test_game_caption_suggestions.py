import hashlib
import unittest

from editorial_draft_suggestions import suggest


def candidate(url, body):
    return {
        "status": "needs_editorial_review",
        "source_url": url,
        "source_body": body,
        "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
    }


class GameCaptionTests(unittest.TestCase):
    def test_win_from_verified_body(self):
        body = "ベルギーリーグ第11節 ズルテ・ワレヘム戦（H）\n結果：4-1"
        result = suggest(candidate("https://stvv.jp/news/game/20261109_1/", body))
        self.assertIsNotNone(result)
        self.assertIn("ズルテ・ワレヘム戦は4-1で勝利", result["text"])
        self.assertFalse(result["reviewed"])
        self.assertFalse(result["auto_publish"])

    def test_draw_from_verified_body(self):
        body = "UEFA カンファレンスリーグ 第3節 SKブラン戦（H）\n結果：1-1"
        result = suggest(candidate("https://stvv.jp/news/game/20261106_1/", body))
        self.assertIsNotNone(result)
        self.assertIn("1-1で引き分け", result["text"])

    def test_reject_modified_body_and_missing_score(self):
        body = "ベルギーリーグ第11節 ズルテ・ワレヘム戦（H）\n結果：4-1"
        item = candidate("https://stvv.jp/news/game/20261109_1/", body)
        item["body_sha256"] = "bad"
        self.assertIsNone(suggest(item))
        self.assertIsNone(suggest(candidate(
            "https://stvv.jp/news/game/20261109_1/",
            "ベルギーリーグ第11節 ズルテ・ワレヘム戦（H）")))


if __name__ == "__main__":
    unittest.main()
