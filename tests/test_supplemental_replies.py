import copy
import unittest

import supplemental_replies as replies


PARENT_ID = "2113772119062372376"
PARENT_URL = f"https://x.com/stvvlabo/status/{PARENT_ID}"
SOURCE = "https://stvv.jp/news/uefa-news/20261023_1/"


def history():
    return {
        "publication_log": [{"key": "approved", "source": SOURCE}],
        "pending_replies": {},
        "used_reply_keys": [],
        "reply_publication_log": [],
    }


def candidate():
    return {
        "parent_key": "approved",
        "parent_x_url": PARENT_URL,
        "parent_post_id": PARENT_ID,
        "text": f"補足です。\n公式：{SOURCE}",
        "source_url": SOURCE,
        "reviewed": True,
        "status": "ready",
    }


class SupplementalReplyTests(unittest.TestCase):
    def test_parent_must_be_own_verified_publication(self):
        for field, value in [("parent_x_url", "https://x.com/other/status/123"),
                             ("parent_post_id", "123"), ("parent_key", "missing")]:
            item = candidate()
            item[field] = value
            with self.subTest(field=field), self.assertRaises(replies.ReplyValidationError):
                replies.validate_candidate(item, history())

    def test_source_must_be_official_and_visible(self):
        for source, text in [("https://example.com/fact", "補足"),
                             (SOURCE, "公式リンクなし")]:
            item = candidate()
            item["source_url"], item["text"] = source, text
            with self.subTest(source=source), self.assertRaises(replies.ReplyValidationError):
                replies.validate_candidate(item, history())

    def test_key_binds_parent_text_and_source(self):
        checked = replies.validate_candidate(candidate(), history())
        self.assertEqual(checked["key"], replies.reply_key(PARENT_ID, checked["text"], SOURCE))

    def test_pending_is_persisted_and_duplicate_never_restaged(self):
        state = history()
        snapshots = []
        key = replies.stage_pending(state, candidate(), lambda value: snapshots.append(copy.deepcopy(value)))
        self.assertIn(key, snapshots[0]["pending_replies"])
        self.assertIsNone(replies.stage_pending(state, candidate(), lambda value: None))

    def test_unknown_transport_result_stays_pending(self):
        state = history()
        key = replies.stage_pending(state, candidate(), lambda value: None)
        replies.mark_transport_unknown(state, key, "timeout", lambda value: None)
        self.assertEqual(state["pending_replies"][key]["state"], "transport_result_unknown")
        self.assertIsNone(replies.stage_pending(state, candidate(), lambda value: None))

    def test_publication_requires_verified_parent_child_relationship(self):
        state = history()
        key = replies.stage_pending(state, candidate(), lambda value: None)
        with self.assertRaises(replies.ReplyValidationError):
            replies.mark_x_verified(state, key, PARENT_URL, PARENT_ID, lambda value: None)
        reply_url = "https://x.com/stvvlabo/status/2113772119062372999"
        replies.mark_x_verified(state, key, reply_url, PARENT_ID, lambda value: None)
        self.assertNotIn(key, state["pending_replies"])
        self.assertIn(key, state["used_reply_keys"])

    def test_missing_transport_blocks_without_history_mutation(self):
        state = history()
        original = copy.deepcopy(state)
        with self.assertRaisesRegex(RuntimeError, "blocked_no_reply_transport"):
            replies.require_reply_transport()
        self.assertEqual(state, original)


if __name__ == "__main__":
    unittest.main()
