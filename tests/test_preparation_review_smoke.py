"""Regression: confirmed external X publications must not enter image review."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from editorial.preparation_review_smoke import run_preparation
from editorial.render_review_svg import render_svg, render_bundle


class PreparationReviewSmokeTests(unittest.TestCase):
    def test_confirmed_x_post_skipped_next_candidate_rendered(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            body = "Verified official body"
            digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
            def candidate(url):
                return {"source_url": url, "status": "needs_editorial_review",
                        "source_body": body, "body_sha256": digest,
                        "date_jst": "2026-11-15", "official_heading": "Official news"}
            prep = root / "preparation.json"
            prep.write_text(json.dumps({"candidates": [
                candidate("https://stvv.jp/news/posted/"),
                candidate("https://stvv.jp/news/new/")
            ], "unapproved_draft_suggestions": [{
                "source_url": "https://stvv.jp/news/new/",
                "status": "draft_unapproved", "source_body_sha256": digest,
                "text": "Official news from STVV."
            }]}), encoding="utf-8")
            external = root / "external.json"
            external.write_text(json.dumps({"items": [{
                "source_url": "https://stvv.jp/news/posted/",
                "status": "confirmed_external_publication"
            }]}), encoding="utf-8")
            result = run_preparation(prep, external, root / "output")
            self.assertEqual(result["confirmed_external_skipped"], 1)
            self.assertEqual(result["candidate_count"], 1)
            self.assertEqual(result["images"][0]["status"], "rendered_unapproved")
            saved = json.loads(Path(result["bundle_path"]).read_text(encoding="utf-8"))
            self.assertTrue(saved["image_generation_performed"])
            self.assertEqual(saved["items"][0]["preview"]["image_status"], "generated_unapproved")
            self.assertTrue(Path(saved["items"][0]["preview"]["image_path"]).is_file())
            self.assertEqual(saved["items"][0]["preview"]["approval_status"], "not_approved")
            self.assertFalse(saved["items"][0]["preview"]["ready_for_buffer"])
            self.assertFalse(saved["buffer_sent"])

            self.assertFalse(result["buffer_sent"])
            self.assertFalse(result["x_published"])


    def test_confirmed_digest_skips_relocated_story(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            body = "Previously published official body"
            digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
            prep = root / "preparation.json"
            prep.write_text(json.dumps({"candidates": [{
                "source_url": "https://stvv.jp/news/relocated/",
                "status": "needs_editorial_review",
                "source_body": body, "body_sha256": digest,
                "date_jst": "2026-11-15", "official_heading": "Relocated story"
            }], "unapproved_draft_suggestions": []}), encoding="utf-8")
            external = root / "external.json"
            external.write_text(json.dumps({"items": [{
                "source_url": "https://stvv.jp/news/original/",
                "source_body_sha256": digest,
                "status": "confirmed_external_publication"
            }]}), encoding="utf-8")
            result = run_preparation(prep, external, root / "output")
            self.assertEqual(result["confirmed_external_skipped"], 1)
            self.assertEqual(result["candidate_count"], 0)
            self.assertEqual(result["images"], [])
            self.assertFalse(result["buffer_sent"])

    def test_fullwidth_round_conflict_skips_candidate_without_blocking_next(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            def candidate(url, heading, body):
                return {"source_url": url, "status": "needs_editorial_review",
                        "source_body": body,
                        "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                        "date_jst": "2026-11-15", "official_heading": heading}
            preparation = root / "preparation.json"
            preparation.write_text(json.dumps({"candidates": [
                candidate("https://stvv.jp/news/round-conflict/",
                          "第２節 試合情報", "試合の概要 " + "説明" * 110 + " 第３節 の試合"),
                candidate("https://stvv.jp/news/next-candidate/",
                          "クラブからのお知らせ", "クラブからの公式案内")
            ], "unapproved_draft_suggestions": [{
                "source_url": "https://stvv.jp/news/next-candidate/",
                "status": "draft_unapproved",
                "source_body_sha256": hashlib.sha256("クラブからの公式案内".encode("utf-8")).hexdigest(),
                "text": "クラブからの公式案内です。"
            }]}, ensure_ascii=False), encoding="utf-8")
            external = root / "external.json"
            external.write_text('{"items":[]}', encoding="utf-8")
            result = run_preparation(preparation, external, root / "output")
            self.assertEqual(result["conflicting_round_skipped"], 1)
            self.assertEqual(result["candidate_count"], 1)
            self.assertEqual(result["images"][0]["status"], "rendered_unapproved")
            self.assertFalse(result["buffer_sent"])

    def test_long_official_headline_uses_caption_on_svg(self):
        digest = "a" * 64
        source = {
            "source_url": "https://stvv.jp/news/event/20261114_1/",
            "official_heading": "小田原市少年サッカー大会" * 9,
            "date_jst": "2026-11-14",
            "caption": "📣 STVVが小田原市の少年少女サッカー大会に特別協賛。",
            "source_body_sha256": digest,
        }
        preview = dict(source, approval_status="not_approved",
                       ready_for_buffer=False, image_status="not_generated")
        brief = dict(source, approval_status="not_approved",
                     ready_for_buffer=False, image_status="brief_only",
                     image_path=None)
        svg = render_svg({"preview": preview, "image_brief": brief})
        self.assertIn("小田原市の少年少女サッカー大会", svg)
        self.assertNotIn("小田原市少年サッカー大会" * 9, svg)

    def test_multiline_caption_does_not_render_second_line_as_title(self):
        digest = "b" * 64
        source = {
            "source_url": "https://stvv.jp/news/event/20261114_1/",
            "official_heading": "小田原市少年サッカー大会" * 9,
            "date_jst": "2026-11-14",
            "caption": "📣 STVVが小田原市の大会に協賛。\n詳細は公式サイトへ。",
            "source_body_sha256": digest,
        }
        preview = dict(source, approval_status="not_approved",
                       ready_for_buffer=False, image_status="not_generated")
        brief = dict(source, approval_status="not_approved",
                     ready_for_buffer=False, image_status="brief_only",
                     image_path=None)
        svg = render_svg({"preview": preview, "image_brief": brief})
        self.assertIn("小田原市の大会に協賛", svg)
        self.assertNotIn("詳細は公式サイトへ", svg)

    def test_japanese_svg_title_lines_fit_canvas(self):
        import re
        import unicodedata
        digest = "c" * 64
        source = {
            "source_url": "https://stvv.jp/news/event/20261114_1/",
            "official_heading": "小田原市少年サッカー大会" * 9,
            "date_jst": "2026-11-14",
            "caption": "📣 STVVが11月21日、小田原市開催予定の少年少女サッカー大会に特別協賛。小学4年生以下の男女計20チームが参加予定です。",
            "source_body_sha256": digest,
        }
        preview = dict(source, approval_status="not_approved",
                       ready_for_buffer=False, image_status="not_generated")
        brief = dict(source, approval_status="not_approved",
                     ready_for_buffer=False, image_status="brief_only", image_path=None)
        svg = render_svg({"preview": preview, "image_brief": brief})
        title_lines = re.findall(r'<text x="90" y="(?:295|365|435)"[^>]*>([^<]*)</text>', svg)
        self.assertGreater(len(title_lines), 0)
        self.assertLessEqual(len(title_lines), 3)
        for line in title_lines:
            units = sum(2 if unicodedata.east_asian_width(ch) in ("F", "W") else 1 for ch in line)
            self.assertLessEqual(units, 36)
        self.assertIn('font-family="Noto Sans CJK JP, sans-serif"', svg)

    def test_odawara_event_generates_unapproved_caption_and_image(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            body = ("2026年11月21日(土)、小田原市で少年少女サッカー大会。"
                    "STVVが特別協賛。小学4年生以下の男女計20チームが参加予定。")
            digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
            url = "https://stvv.jp/news/event/20261114_1/"
            prep = root / "preparation.json"
            prep.write_text(json.dumps({"candidates": [{
                "source_url": url, "status": "needs_editorial_review",
                "source_body": body, "body_sha256": digest,
                "date_jst": "2026-11-14", "official_heading": "少年サッカー大会"
            }], "unapproved_draft_suggestions": []}, ensure_ascii=False), encoding="utf-8")
            external = root / "external.json"
            external.write_text('{"items":[]}', encoding="utf-8")
            result = run_preparation(prep, external, root / "review")
            self.assertEqual(result["candidate_count"], 1)
            self.assertEqual(result["images"][0]["status"], "rendered_unapproved")
            self.assertFalse(result["buffer_sent"])
            self.assertFalse(result["x_published"])

    def test_three_candidate_fixture_skips_two_published_and_conflicting_round(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            def candidate(url, heading, body):
                return {"source_url": url, "status": "needs_editorial_review",
                        "source_body": body,
                        "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                        "date_jst": "2026-11-15", "official_heading": heading}
            posted_a = "https://stvv.jp/news/game/posted/"
            posted_b = "https://stvv.jp/news/team/posted/"
            conflict = "https://stvv.jp/news/game/conflicting/"
            preparation = root / "preparation.json"
            preparation.write_text(json.dumps({"candidates": [
                candidate(posted_a, "Match", "Verified match report"),
                candidate(posted_b, "Coach", "Verified coach announcement"),
                candidate(conflict, "第2節 SKブラン戦", "第3節 SKブラン戦")
            ], "unapproved_draft_suggestions": []}), encoding="utf-8")
            external = root / "external.json"
            external.write_text(json.dumps({"items": [
                {"source_url": posted_a, "status": "confirmed_external_publication"},
                {"source_url": posted_b, "status": "confirmed_external_publication"}
            ]}), encoding="utf-8")
            result = run_preparation(preparation, external, root / "review")
            self.assertEqual(result["confirmed_external_skipped"], 2)
            self.assertEqual(result["conflicting_round_skipped"], 1)
            self.assertEqual(result["candidate_count"], 0)
            self.assertEqual(result["images"], [])
            self.assertFalse(result["buffer_sent"])
            self.assertFalse(result["x_published"])


    def test_same_official_url_different_digest_renders_once(self):
        with tempfile.TemporaryDirectory() as temp:
            def item(digest):
                source = {
                    "source_url": "https://stvv.jp/news/event/same-story/",
                    "official_heading": "Official event",
                    "date_jst": "2026-11-16",
                    "caption": "Official event",
                    "source_body_sha256": digest,
                }
                return {
                    "preview": dict(source, approval_status="not_approved",
                                    ready_for_buffer=False, image_status="not_generated"),
                    "image_brief": dict(source, approval_status="not_approved",
                                        ready_for_buffer=False, image_status="brief_only",
                                        image_path=None),
                }
            result = render_bundle({
                "status": "review_required",
                "items": [item("a" * 64), item("b" * 64)],
            }, Path(temp))
            self.assertEqual([x["status"] for x in result["images"]],
                             ["rendered_unapproved", "skipped"])
            self.assertEqual(result["images"][1]["reason"], "Duplicate source URL")
            self.assertEqual(len(list(Path(temp).glob("*.svg"))), 1)
            self.assertFalse(result["buffer_sent"])
            self.assertFalse(result["x_published"])


if __name__ == "__main__":
    unittest.main()
