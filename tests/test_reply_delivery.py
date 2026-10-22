"""A supplemental reply must never be silently published as a new root."""
import copy
import unittest
from unittest.mock import patch

import stvv_post as posting


class ReplyDeliveryTests(unittest.TestCase):
    def test_reply_rejected_before_network(self):
        for parent in ('https://x.com/stvvlabo/status/123', '', '123'):
            with self.subTest(parent=parent), patch.object(posting.SESSION, 'post') as network:
                with self.assertRaisesRegex(RuntimeError, 'blocked_unsupported_reply'):
                    posting.send('supplement', reply_to=parent)
                network.assert_not_called()

    def test_reply_rejected_without_pending_or_publication_mutation(self):
        history = {'used_posts': [], 'pending_posts': {}, 'publication_log': []}
        original = copy.deepcopy(history)
        with patch.object(posting, 'save') as save, patch.object(posting, 'send') as send:
            with self.assertRaisesRegex(RuntimeError, 'blocked_unsupported_reply'):
                posting.publish(history, 'reply', 'supplement', 'analysis', reply_to='123')
            save.assert_not_called()
            send.assert_not_called()
        self.assertEqual(history, original)
