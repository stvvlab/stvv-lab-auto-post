import unittest
from visual_rotation import choose_variant, VISUAL_POLICY, APPROVED_VARIANTS


class VisualRotationTests(unittest.TestCase):
    def test_old_history_preserves_previous_rotation(self):
        self.assertEqual(choose_variant({"publication_log": [{}, {}]}), "poster")

    def test_never_repeat_previous_known_variant(self):
        for name in APPROVED_VARIANTS:
            result = choose_variant({"publication_log": [{"visual_variant": name}]})
            self.assertNotEqual(result, name)

    def test_pending_does_not_advance_rotation(self):
        log = [{"visual_variant": "split"}]
        self.assertEqual(choose_variant({"publication_log": log}), choose_variant({
            "publication_log": log,
            "pending_posts": {"k": {"visual_variant": "poster"}}
        }))

    def test_policy_does_not_claim_ai_art_is_enabled(self):
        self.assertFalse(VISUAL_POLICY["speech_bubbles"])
        self.assertEqual(len(VISUAL_POLICY["future_art_directions"]), 12)


if __name__ == "__main__":
    unittest.main()
