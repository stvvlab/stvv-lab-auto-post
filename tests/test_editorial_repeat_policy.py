"""An approved editorial purpose may be repeated usefully, never blindly."""
import unittest
from datetime import datetime, timedelta, timezone
from editorial_repeat_policy import value_based_repeat_reason

NOW = datetime(2026, 10, 29, 21, tzinfo=timezone(timedelta(hours=9)))
SOURCE = 'https://stvv.com/nl/nieuws/artikel/de-week-van-de-waarheid'
EVENT = 'stvv-ohl-2026-11-02'


def card(kind='fixture', phase='initial', text='STVV vs OH Leuven 次戦はホーム！'):
    return {'status': 'ready', 'reviewed': True, 'text': text,
            'source_url': SOURCE,
            'editorial_purpose': {'kind': kind, 'phase': phase, 'event_id': EVENT}}


def history():
    return {'news': ['https://stvv.jp/news/event/20261002_2/'],
            'publication_log': [], 'pending_posts': {}, 'reserved_posts': {}}


class ValueBasedRepeatTests(unittest.TestCase):
    def test_official_site_prior_announcement_does_not_block_first_lab_post(self):
        self.assertIsNone(value_based_repeat_reason(history(), card(), NOW))

    def test_explicit_fixture_reminder_after_previous_publication_is_allowed(self):
        h = history()
        h['publication_log'].append({
            'text': '3日前 STVV vs OH Leuven',
            'source': SOURCE, 'submitted_at': (NOW - timedelta(days=2)).isoformat(),
            'editorial_purpose': {'kind': 'fixture', 'phase': 'initial', 'event_id': EVENT}})
        self.assertIsNone(value_based_repeat_reason(h, card(phase='reminder',
            text='明日0時 STVV vs OH Leuven ホーム戦！'), NOW))

    def test_same_purpose_repeated_too_soon_is_blocked(self):
        h = history()
        h['publication_log'].append({
            'text': 'STVV vs OH Leuven ホーム戦案内',
            'submitted_at': (NOW - timedelta(hours=2)).isoformat(),
            'editorial_purpose': card()['editorial_purpose']})
        self.assertEqual(value_based_repeat_reason(h, card(text='同じ試合の追加告知'), NOW),
                         'same_purpose_published_within_24h')

    def test_identical_caption_is_blocked_even_with_other_phase(self):
        h = history()
        h['publication_log'].append({'text': card()['text'], 'source': SOURCE})
        self.assertEqual(value_based_repeat_reason(h, card(phase='reminder'), NOW),
                         'identical_caption_already_sent_or_pending')

    def test_pending_and_reservation_of_same_purpose_are_blocked(self):
        for field in ('pending_posts', 'reserved_posts'):
            h = history()
            h[field]['post'] = {'text': '別の表現',
                 'editorial_purpose': card()['editorial_purpose']}
            with self.subTest(field=field):
                self.assertEqual(value_based_repeat_reason(h, card(), NOW),
                                 'same_purpose_pending_or_reserved')

    def test_distinct_analysis_of_same_match_is_allowed(self):
        h = history()
        h['publication_log'].append({
            'text': '試合結果 STVV 2-1 OH Leuven',
            'editorial_purpose': {'kind':'result', 'phase':'final', 'event_id':EVENT},
            'submitted_at': NOW.isoformat()})
        self.assertIsNone(value_based_repeat_reason(h, card(
            kind='analysis', phase='review', text='中盤の距離感を検証'), NOW))

    def test_missing_approval_or_identity_fails_closed(self):
        for change in ({'reviewed': False},
                       {'status': 'draft'},
                       {'editorial_purpose': {'kind':'fixture','phase':'initial','event_id':'bad space'}}):
            c = card()
            c.update(change)
            self.assertEqual(value_based_repeat_reason(history(), c, NOW),
                             'invalid_reviewed_editorial_purpose')


if __name__ == '__main__':
    unittest.main()
