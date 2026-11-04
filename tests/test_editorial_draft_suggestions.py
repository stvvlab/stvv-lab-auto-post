import hashlib
import unittest
from editorial_draft_suggestions import suggest, suggestions


def item(body, url):
    return {'status': 'needs_editorial_review', 'source_body': body,
            'body_sha256': hashlib.sha256(body.encode()).hexdigest(),
            'source_url': url}


class EditorialDraftSuggestionTests(unittest.TestCase):
    def test_contract_termination_is_draft_only(self):
        body = ('この度、フレデリック・デ・メイヤー監督との契約を解除いたしましたので、お知らせいたします。'
                '新監督については決定次第お知らせします。')
        draft = suggest(item(body, 'https://stvv.jp/news/team/20261102_2/'))
        self.assertIsNotNone(draft)
        self.assertIn('契約を解除', draft['text'])
        self.assertNotIn('新監督', draft['text'])
        self.assertFalse(draft['reviewed'])
        self.assertFalse(draft['auto_publish'])

    def test_event_draft_requires_all_source_facts(self):
        body = '2026年11月29日（日）にゲンク戦の観戦会を開催。参加費は無料です。'
        draft = suggest(item(body, 'https://stvv.jp/news/event/20261030_2/'))
        self.assertIn('参加費は無料', draft['text'])
        self.assertIsNone(suggest(item(body.replace('無料', '有料'),
                                         'https://stvv.jp/news/event/20261030_2/')))

    def test_digest_tamper_untrusted_source_and_nonready_fail_closed(self):
        body = 'フレデリック・デ・メイヤー監督との契約を解除いたしました。'
        original = item(body, 'https://stvv.jp/news/team/20261102_2/')
        original['body_sha256'] = '0' * 64
        self.assertIsNone(suggest(original))
        self.assertIsNone(suggest(item(body, 'https://evil.example/news/team/20261102_2/')))
        original = item(body, 'https://stvv.jp/news/team/20261102_2/')
        original['status'] = 'source_unavailable'
        self.assertEqual(suggestions({'candidates': [original]}), [])


if __name__ == '__main__':
    unittest.main()
