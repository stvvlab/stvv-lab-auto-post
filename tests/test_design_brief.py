import unittest
from design_brief import build_brief, choose_art_direction, ART_DIRECTIONS


class DesignBriefTests(unittest.TestCase):
    source = "https://stvv.jp/news/uefa-news/20261023_1/"

    def test_each_direction_can_rotate_without_repeating(self):
        history = {"publication_log": []}
        for _ in ART_DIRECTIONS:
            direction = choose_art_direction(history, self.source)
            self.assertNotIn(direction, [p["art_direction"] for p in history["publication_log"]])
            history["publication_log"].append({"art_direction": direction})

    def test_pending_does_not_consume_style(self):
        base = {"publication_log": [{"art_direction": "comic-cover"}]}
        self.assertEqual(choose_art_direction(base, self.source), choose_art_direction(
            dict(base, pending_posts={"x": {"art_direction": "ink-poster"}}), self.source))

    def test_brief_is_not_a_reviewed_asset(self):
        brief = build_brief(self.source, "確認済みの本文 " + self.source, {})
        self.assertEqual(brief["status"], "brief_only")
        self.assertNotIn("reviewed", brief)
        self.assertNotIn("asset_path", brief)
        self.assertIn("No speech bubbles", brief["prompt"])

    def test_variations_are_in_brief_and_exclude_rejected_style(self):
        brief = build_brief(self.source, "確認済みの本文 " + self.source, {})
        self.assertNotIn("abstract-motion", ART_DIRECTIONS)
        self.assertEqual(set(brief["visual_variation"]), {"composition", "motif", "texture"})
        for choice in brief["visual_variation"].values():
            self.assertIn(choice, brief["prompt"])
        self.assertIn("Fictional non-human creatures only", brief["prompt"])

    def test_repeated_published_variations_rotate(self):
        from design_brief import visual_variation
        history = {"publication_log": []}
        for _ in range(4):
            current = visual_variation(self.source, "comic-cover", history)
            if history["publication_log"]:
                previous = history["publication_log"][-1]
                for field in ("composition", "motif", "texture"):
                    self.assertNotEqual(current[field], previous[field])
            history["publication_log"].append(dict(current, art_direction="comic-cover"))
        self.assertEqual(4, len({p["composition"] for p in history["publication_log"]}))

    def test_invalid_source_or_missing_citation_rejected(self):
        for source, text in [("https://stvv.jp.evil/news/a", "text"), (self.source, "no source")]:
            with self.assertRaises(ValueError):
                build_brief(source, text, {})
