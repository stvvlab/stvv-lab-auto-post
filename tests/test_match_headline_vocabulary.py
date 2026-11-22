"""Regression tests for actual STVV match-headline vocabulary (2026-11-22)."""
from datetime import datetime
from zoneinfo import ZoneInfo

from official_sources import parse_articles

NOW = datetime(2026, 11, 23, tzinfo=ZoneInfo("Asia/Tokyo"))

def card(title, date="20261122"):
    return (f'<a href="/news/game/{date}example/"><h3>{title}</h3>'
            '<p>ベルギーリーグ第12節、2-2の結果。</p></a>')

def test_goal_and_draw_match_headline_is_eligible():
    headline = "90分に執念の同点ゴール！激闘のシャルルロワ戦は2-2のドロー決着！"
    results = parse_articles(card(headline), NOW)
    assert len(results) == 1
    assert results[0][1][1] == headline

def test_sponsor_headline_remains_excluded():
    assert parse_articles(card("スポンサー契約記念ゴールキャンペーン"), NOW) == []

def test_old_goal_headline_remains_excluded():
    assert parse_articles(card("90分に同点ゴール！ドロー決着", "20261109"), NOW) == []
