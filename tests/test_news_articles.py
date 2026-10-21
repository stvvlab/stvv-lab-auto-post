"""Official listing headings must not absorb dates or preview paragraphs."""
import unittest
from datetime import datetime
from unittest.mock import patch, Mock
import stvv_post as posting


class NewsArticleTests(unittest.TestCase):
    def articles_from(self, markup):
        response = Mock(text=markup)
        now = datetime(2026, 10, 21, 18, tzinfo=posting.JST)
        with patch.object(posting.SESSION, 'get', return_value=response):
            return posting.articles(now)

    def test_card_heading_excludes_time_and_long_excerpt(self):
        title = '日本人選手の試合出場について'
        markup = ('<a href="/news/team/20261021_1/"><img alt=""></a>'
                  '<a href="/news/team/20261021_1/">'
                  '<h3><span><time>2026.10.21</time></span>' + title + '</h3>'
                  '<p>' + '本文の抜粋。' * 100 + '</p></a>')
        articles = self.articles_from(markup)
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0][1][1], title)
        message = '📰 STVV公式ニュース\n' + articles[0][1][1] + '\n🔗 ' + articles[0][0]
        self.assertLessEqual(posting.x_length(message + posting.HASHTAGS), 270)

    def test_plain_links_remain_supported_and_source_filters_stay_in_place(self):
        markup = '''<a href="/news/team/20261021_1/">選手の試合出場について</a>
        <a href="/news/team/20261021_2/"><h3>選手とのスポンサー契約について</h3></a>
        <a href="/news/team/20261021_5/"><h3>選手の試合出場について</h3><p>スポンサー企画</p></a>
        <a href="https://example.test/news/team/20261021_3/"><h3>選手の試合出場について</h3></a>
        <a href="/news/team/20261001_4/"><h3>選手の試合出場について</h3></a>'''
        articles = self.articles_from(markup)
        self.assertEqual([url for url, _ in articles], ['https://stvv.jp/news/team/20261021_1/'])
