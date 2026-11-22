"""Regression tests for STVV match headline vocabulary and promotional filtering."""
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from official_sources import parse_articles

NOW = datetime(2026, 11, 23, tzinfo=ZoneInfo("Asia/Tokyo"))

def card(title, date="20261122", excerpt="ベルギーリーグ第12節、2-2の結果。"):
    return (f'<a href="/news/game/{date}example/"><h3>{title}</h3>'
            f'<p>{excerpt}</p></a>')

class MatchHeadlineVocabularyTests(unittest.TestCase):
    def test_goal_and_draw_match_headline_is_eligible(self):
        headline = "90分に執念の同点ゴール！激闘のシャルルロワ戦は2-2のドロー決着！"
        results = parse_articles(card(headline), NOW)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][1][1], headline)

    def test_sponsor_headline_remains_excluded(self):
        self.assertEqual(parse_articles(card("スポンサー契約記念ゴールキャンペーン"), NOW), [])

    def test_old_goal_headline_remains_excluded(self):
        self.assertEqual(parse_articles(card("90分に同点ゴール！ドロー決着", "20261109"), NOW), [])

    def test_promotional_excerpt_does_not_hide_match(self):
        headline = "90分に同点ゴール！ドロー決着"
        self.assertEqual(len(parse_articles(card(headline, excerpt="スポンサー情報はこちら"), NOW)), 1)

if __name__ == "__main__":
    unittest.main()
