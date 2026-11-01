import unittest
from editorial_review import review


class EditorialReviewTests(unittest.TestCase):
    def test_incomplete_review_is_not_invented(self):
        result = review({"kind": "news", "ratings": {"accuracy": 1}})
        self.assertEqual(result["status"], "unscored")
        self.assertEqual(result["publication_decision"], "unchanged")

    def test_low_dimension_gets_advice(self):
        ratings = dict.fromkeys(("accuracy", "analysis", "engagement",
                                 "clarity", "visual", "variety"), 1)
        ratings["analysis"] = 0.2
        result = review({"kind": "player", "ratings": ratings})
        self.assertEqual(result["status"], "improve")
        self.assertTrue(any("試合局面" in s for s in result["suggestions"]))
        self.assertEqual(result["publication_decision"], "unchanged")


if __name__ == "__main__":
    unittest.main()
