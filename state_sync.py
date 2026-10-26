"""Persist posting state despite concurrent report-only commits, never resend."""
import subprocess
from pathlib import Path


def command(root, *args):
    return subprocess.run(['git', *args], cwd=root, check=True,
                          capture_output=True, text=True).stdout.strip()


def push_posting_state(root=None):
    root = Path(root or Path(__file__).resolve().parent)
    for attempt in range(3):
        try:
            command(root, 'push', 'origin', 'HEAD:main')
            return
        except subprocess.CalledProcessError as error:
            if attempt == 2:
                raise RuntimeError('Posting state push failed; do not resend') from error
            # Only the single new posting-state commit can be replayed. Never
            # resolve history, reviewed-image or code conflicts automatically.
            parent = command(root, 'rev-parse', 'HEAD^')
            local_paths = command(root, 'diff', '--name-only', parent, 'HEAD').splitlines()
            if local_paths != ['posted.json']:
                raise RuntimeError('State recovery requires one posting-ledger commit') from error
            command(root, 'fetch', 'origin', 'main')
            remote = command(root, 'rev-parse', 'FETCH_HEAD')
            if remote == parent:
                raise RuntimeError('Push failed without concurrent advancement; do not resend') from error
            try:
                command(root, 'merge-base', '--is-ancestor', parent, remote)
            except subprocess.CalledProcessError:
                raise RuntimeError('Remote history diverged; manual review required') from error
            changed = command(root, 'diff', '--name-only', parent, remote).splitlines()
            # Allowlist report-only changes, including no ledger, manifest,
            # source, configuration, or generated-asset changes.
            if not changed or any(not p.startswith('reports/') for p in changed):
                raise RuntimeError('Remote publication inputs changed; do not resend') from error
            if command(root, 'status', '--porcelain', '--untracked-files=no'):
                raise RuntimeError('Tracked worktree changes prevent safe state recovery') from error
            command(root, 'rebase', remote)
    raise RuntimeError('Posting state was not persisted')
