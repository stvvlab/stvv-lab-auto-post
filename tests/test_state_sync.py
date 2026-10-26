"""Exercise real competing git writers locally; no network or publication."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from state_sync import command, push_posting_state


class StateSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.remote = self.root / 'remote.git'
        self.a, self.b = self.root / 'a', self.root / 'b'
        self.a.mkdir()
        command(self.root, 'init', '--bare', '--initial-branch=main', str(self.remote))
        command(self.a, 'init', '--initial-branch=main')
        self.configure(self.a)
        self.commit(self.a, 'posted.json', '{"pending_posts":{}}')
        command(self.a, 'remote', 'add', 'origin', str(self.remote))
        command(self.a, 'push', '-u', 'origin', 'main')
        command(self.root, 'clone', str(self.remote), str(self.b))
        self.configure(self.b)

    def configure(self, repo):
        command(repo, 'config', 'user.name', 'Offline test')
        command(repo, 'config', 'user.email', 'test@example.invalid')

    def commit(self, repo, path, content):
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        command(repo, 'add', path)
        command(repo, 'commit', '-m', 'offline fixture')

    def remote_file(self, path):
        return command(self.remote, 'show', f'main:{path}')

    def test_pending_saved_after_report_race(self):
        pending = '{"pending_posts":{"k":{"text":"verified"}}}'
        self.commit(self.a, 'posted.json', pending)
        self.commit(self.b, 'reports/preparation.json', '{"candidate":1}')
        command(self.b, 'push')
        push_posting_state(self.a)
        self.assertEqual(json.loads(self.remote_file('posted.json')), json.loads(pending))
        self.assertEqual(self.remote_file('reports/preparation.json'), '{"candidate":1}')

    def test_competing_ledger_blocks_without_overwrite(self):
        self.commit(self.a, 'posted.json', '{"pending_posts":{"local":{}}}')
        self.commit(self.b, 'posted.json', '{"pending_posts":{"other":{}}}')
        command(self.b, 'push')
        with self.assertRaisesRegex(RuntimeError, 'publication inputs changed'):
            push_posting_state(self.a)
        self.assertIn('other', json.loads(self.remote_file('posted.json'))['pending_posts'])
        self.assertNotIn('local', json.loads(self.remote_file('posted.json'))['pending_posts'])

    def test_changed_reviewed_manifest_blocks(self):
        self.commit(self.a, 'posted.json', '{"pending_posts":{"local":{}}}')
        self.commit(self.b, 'editorial/imagegen_cards.json', '{"enabled":false}')
        command(self.b, 'push')
        with self.assertRaisesRegex(RuntimeError, 'publication inputs changed'):
            push_posting_state(self.a)
        self.assertEqual(json.loads(self.remote_file('posted.json'))['pending_posts'], {})

    def test_acceptance_saved_after_report_race(self):
        # Pending was durably published first; then a report writer intervenes.
        self.commit(self.a, 'posted.json', '{"pending_posts":{"k":{}}}')
        push_posting_state(self.a)
        command(self.b, 'pull', '--ff-only')
        self.commit(self.b, 'reports/preparation.json', '{}')
        command(self.b, 'push')
        accepted = '{"pending_posts":{},"publication_log":[{"key":"k","buffer_id":"fixture"}]}'
        self.commit(self.a, 'posted.json', accepted)
        push_posting_state(self.a)
        self.assertEqual(json.loads(self.remote_file('posted.json')), json.loads(accepted))
