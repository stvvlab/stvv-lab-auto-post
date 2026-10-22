import argparse
from dataclasses import asdict
from datetime import datetime
import json
import os
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from .engine import Snapshot, plan, verify
from .source import fetch, parse_schedule


def dump(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def summary(report):
    return '\n'.join([
        '# STVV LAB データベース更新', '',
        f"状態：{report['status']}",
        f"追加：{report.get('added_rows', 0)}行",
        f"修正：{report.get('modified_rows', 0)}行 / {report.get('modified_cells', 0)}セル",
        f"運用メモ：{report.get('note_cells', 0)}セル", '並べ替え：なし',
        f"公式照合：{report.get('checked_matches', 0)}試合",
        f"再読み込み検証：{report.get('verification', '未実施')}",
        f"今回の照合保留：{len(report.get('pending', []))}件。",
        '未完了：詳細統計・個人記録・得点イベントの自動補完、新規試合のID発番。',
        f"エラー：{'; '.join(report.get('errors', [])) or 'なし'}", '',
        '※ 完了とは再読検証済みの変更のみ。データ全件補完の完了を意味しません。', ''])


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--write-test', action='store_true', help='Write only a dedicated operations note if no data changes')
    parser.add_argument('--snapshot', help='Offline/connector snapshot; emits plan only, never applies')
    parser.add_argument('--html-dir', help='Read previously fetched official HTML for reproducible validation')
    parser.add_argument('--out', default='reports/database')
    args = parser.parse_args(argv)
    out = Path(args.out)
    report = {'started_at': datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(),
              'status': 'failed', 'added_rows': 0, 'modified_rows': 0, 'modified_cells': 0,
              'note_cells': 0, 'sorted': False, 'verification': '未実施', 'errors': [],
              'pending': [], 'coverage': 'existing_match_results_only', 'sources': []}
    try:
        matches = []
        for season, slug in [('2025/26', '2025-2026'), ('2026/27', '2026-2027')]:
            url = f'https://stvv.jp/game/{slug}/'
            html = Path(args.html_dir, slug + '.html').read_text(encoding='utf-8') if args.html_dir else fetch(url)
            parsed = parse_schedule(html, season, url)
            matches.extend(parsed)
            report['sources'].append({'url': url, 'sha256': parsed[0].digest, 'match_count': len(parsed)})
        if args.snapshot:
            if args.apply:
                raise ValueError('--snapshot cannot be combined with --apply')
            before = Snapshot(json.loads(Path(args.snapshot).read_text(encoding='utf-8')))
        else:
            from .google_client import GoogleSheets
            client = GoogleSheets()
            before = client.read()
        changes, info = plan(before, matches, heartbeat=args.write_test)
        report.update(info)
        requests = [c.request(before) for c in changes]
        if args.snapshot:
            # Plans may contain workbook text. Keep them local; never upload them as CI artifacts.
            dump(out / 'plan.private.json', {'spreadsheet_id': before.raw['spreadsheetId'],
                'snapshot_fingerprint': before.fingerprint(), 'requests': requests,
                'changes': [asdict(c) for c in changes]})
        report['planned_cells'] = sum(c.field == 'userEnteredValue' for c in changes)
        if args.apply:
            fresh = client.read()
            if before.fingerprint() != fresh.fingerprint():
                raise RuntimeError('Workbook changed during collection; no write sent')
            if requests:
                try:
                    client.write(requests)
                except Exception:
                    # A timeout is not proof of failure. Never retry blindly.
                    try:
                        after = client.read()
                        verify(before, after, changes)
                    except Exception:
                        report['verification'] = '書込結果不確定。再試行前に確認が必要'
                        raise RuntimeError('Write failed or result uncertain; no automatic retry') from None
                    report['warnings'] = ['Write response failed, but every intended change was confirmed by a separate read']
                else:
                    verify(before, client.read(), changes)
                report['modified_cells'] = sum(c.field == 'userEnteredValue' for c in changes)
                report['modified_rows'] = len({(c.tab, c.row) for c in changes if c.field == 'userEnteredValue'})
                report['note_cells'] = sum(c.field == 'note' for c in changes)
            else:
                verify(before, fresh, [])
            report['verification'] = '成功'
            report['status'] = 'verified' if requests else 'verified_no_change'
        else:
            report['status'] = 'planned_only'
        returncode = 0
    except Exception as exc:
        # Avoid dumping request payloads or authentication exception bodies.
        report['errors'] = [str(exc)] if isinstance(exc, (ValueError, RuntimeError)) else [type(exc).__name__]
        report['status'] = 'blocked' if 'CREDENTIALS' in ' '.join(report['errors']) else 'failed'
        returncode = 2
    report['finished_at'] = datetime.now(ZoneInfo('Asia/Tokyo')).isoformat()
    dump(out / 'latest.json', report)
    (out / 'latest.md').write_text(summary(report), encoding='utf-8')
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
            f.write(summary(report))
    print(summary(report))
    return returncode


if __name__ == '__main__':
    sys.exit(main())
