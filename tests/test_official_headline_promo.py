"""Regression checks for official headline promotional filtering."""
from datetime import datetime
from zoneinfo import ZoneInfo

from official_sources import parse_articles


NOW = datetime(2026, 11, 22, tzinfo=ZoneInfo("Asia/Tokyo"))


def card(title, excerpt, section="team"):
    return (f'<a href="/news/{section}/20261121sample/">'
            f'<h3>{title}</h3><p>{excerpt}</p></a>')


def test_match_story_survives_promotional_excerpt():
    results = parse_articles(card("選手が試合で勝利", "スポンサー協賛キャンペーンのお知らせ"), NOW)
    assert len(results) == 1


def test_promotional_headline_still_excluded():
    results = parse_articles(card("スポンサー契約選手の試合キャンペーン", "試合速報"), NOW)
    assert results == []


def test_watch_party_survives_giveaway_excerpt():
    results = parse_articles(card("試合観戦会のお知らせ", "プレゼント抽選あり", "event"), NOW)
    assert len(results) == 1


def test_other_event_remains_excluded():
    results = parse_articles(card("選手参加のイベント開催", "試合情報", "event"), NOW)
    assert results == []
