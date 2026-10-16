"""Test live copy without Buffer requests or posting."""
import unittest
import stvv_post as p
from style_posts import STYLE_POSTS

class StyleTests(unittest.TestCase):
    def test_all_slots_have_four_options(self):
        self.assertEqual(set(STYLE_POSTS), set(p.TOPICS))
        for slot, options in STYLE_POSTS.items():
            self.assertGreaterEqual(len(options), 4)
            for style, message in options:
                self.assertTrue(style)
                self.assertTrue(message.strip())
                self.assertLessEqual(p.x_length(message + p.HASHTAGS), 270)
                self.assertFalse(any(word in message for word in p.SPONSORS))

    def test_new_copy_is_used_when_no_verified_event(self):
        for slot in p.TOPICS:
            message = p.choose_fallback(slot, "2026-10-16", {}, {}, [])
            self.assertIn(message, [x[1] for x in STYLE_POSTS[slot]])

    def test_manual_low_score_is_excluded(self):
        for slot in p.TOPICS:
            candidates = [x[1] for x in STYLE_POSTS[slot]]
            excluded = {x: 1 for x in candidates[:3]}
            result = p.choose_fallback(slot, "2026-10-16", excluded, {}, [])
            self.assertEqual(result, candidates[-1])

    def test_recently_used_copy_is_avoided(self):
        slot = "analysis"
        day = "2026-10-16"
        first = p.choose_fallback(slot, day, {}, {}, [])
        history = [{"text": first + p.HASHTAGS}]
        second = p.choose_fallback(slot, day, {}, {}, history)
        self.assertNotEqual(first, second)

if __name__ == "__main__":
    unittest.main()
