import unittest
from editorial_preflight import preflight


class PreflightTests(unittest.TestCase):
    def test_missing_text_blocks(self):
        result = preflight({'post': {'text': ''}})
        self.assertEqual(result['publication_decision'], 'block')

    def test_unrated_remains_unscored(self):
        result = preflight({'post': {'text': 'テスト投稿'}})
        self.assertEqual(result['editorial']['status'], 'unscored')

    def test_quality_advice_does_not_block(self):
        ratings = dict.fromkeys(('accuracy', 'analysis', 'engagement', 'clarity', 'visual', 'variety'), 0)
        result = preflight({'post': {'text': 'テスト投稿'}, 'review': {'kind': 'news', 'ratings': ratings}})
        self.assertEqual(result['publication_decision'], 'pass')
        self.assertEqual(result['editorial']['status'], 'improve')


if __name__ == '__main__':
    unittest.main()
