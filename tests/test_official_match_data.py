"""Official fallback never invents or publishes data without live evidence."""
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
import official_match_data as official
from stvv_post import x_length, HASHTAGS

class OfficialMatchDataTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 21, tzinfo=timezone(timedelta(hours=9)))
        self.text = ('2026.10.19 ロンメル戦（H） 10月19日(月) 結果：4-1 '
                     'STVV：松澤海斗（15分）、新川志音（39分）、ソエル・ソエル（62分）、ムブク（71分）')
        self.session = Mock()
        self.session.get.return_value.url = 'https://stvv.jp/news/game/20261019_1/'
        self.session.get.return_value.text = self.text

    def test_verified_facts_fit_caption_and_keep_official_source(self):
        message, source = official.scoring_data(self.session, self.now)
        self.assertIn('松澤海斗：15分', message)
        self.assertIn('ムブク：71分', message)
        self.assertIn(source, message)
        self.assertLessEqual(x_length(message + HASHTAGS), 270)

    def test_missing_or_changed_official_evidence_blocks_data(self):
        for text in [self.text.replace('15分', '16分'),
                     self.text.replace('結果：4-1', '結果：3-1'),
                     self.text.replace('10月19日', '10月20日'),
                     '<script>' + self.text + '</script>']:
            self.session.get.return_value.text = text
            self.assertIsNone(official.scoring_data(self.session, self.now))

    def test_expired_fact_does_not_fetch_or_publish(self):
        self.assertIsNone(official.scoring_data(self.session, self.now + timedelta(days=8)))
        self.session.get.assert_not_called()

    def test_external_redirect_blocks_data(self):
        self.session.get.return_value.url = 'https://example.org/'
        self.assertIsNone(official.scoring_data(self.session, self.now))
