import unittest
from editorial_score import evaluate


class EditorialScoreTests(unittest.TestCase):
    def test_perfect(self):
        r = evaluate(dict.fromkeys(("accuracy", "analysis", "engagement",
                                    "clarity", "visual", "variety"), 1), kind="feature")
        self.assertEqual(r["score"], 100)
        self.assertEqual(r["status"], "target_met")

    def test_missing_is_unscored(self):
        self.assertEqual(evaluate({"accuracy": 1})["status"], "unscored")

    def test_text_only_normalized(self):
        r = evaluate(dict.fromkeys(("accuracy", "analysis", "engagement",
                                    "clarity", "variety"), 0.9), text_only=True)
        self.assertEqual(r["score"], 90)

    def test_low_score_never_blocks(self):
        r = evaluate(dict.fromkeys(("accuracy", "analysis", "engagement",
                                    "clarity", "visual", "variety"), 0))
        self.assertEqual(r["publication_decision"], "unchanged")
        self.assertEqual(r["status"], "improve")

    def test_invalid_rating(self):
        with self.assertRaises(ValueError):
            evaluate({"accuracy": 1.5})


if __name__ == "__main__":
    unittest.main()
