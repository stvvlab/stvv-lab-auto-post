"""Standalone Sheets authentication. Connector tokens are never extracted."""
import json
import os
import time

from .engine import SHEET_ID, TABS, Snapshot

FIELDS = ('userEnteredValue,effectiveValue,userEnteredFormat,dataValidation,note,chipRuns,'
          'effectiveFormat(textFormat(link)),hyperlink')


class GoogleSheets:
    def __init__(self):
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account
        payload = os.getenv('STVV_DB_GOOGLE_CREDENTIALS')
        if not payload:
            raise RuntimeError('STVV_DB_GOOGLE_CREDENTIALS is not configured')
        try:
            info = json.loads(payload)
            credentials = service_account.Credentials.from_service_account_info(
                info, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        except Exception:
            # Never expose the credential document, JSON decoder excerpt or key.
            raise RuntimeError('Invalid STVV_DB_GOOGLE_CREDENTIALS configuration') from None
        self.session = AuthorizedSession(credentials)
        self.base = f'https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}'

    def get(self, url, params):
        for attempt in range(4):
            response = self.session.get(url, params=params, timeout=(10, 40))
            if response.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(min(2 ** attempt, 8))
                continue
            if not response.ok:
                raise RuntimeError(f'Sheets read failed (HTTP {response.status_code})')
            return response.json()
        raise RuntimeError('Sheets read retries exhausted')

    def read(self):
        metadata = self.get(self.base, {'fields': 'spreadsheetId,properties,sheets(properties)'})
        if tuple(s['properties']['title'] for s in metadata['sheets']) != TABS:
            raise ValueError('The existing eight tabs changed')
        ranges = []
        for s in metadata['sheets']:
            p = s['properties']
            rows = p['gridProperties']['rowCount']
            if rows > 10000 or p['gridProperties']['columnCount'] > 100:
                raise ValueError('Workbook bounds changed; manual review required')
            ranges.append(f"'{p['title']}'!A1:A{rows}")
        used = self.get(self.base + '/values:batchGet', [('ranges', r) for r in ranges])
        data_ranges = []
        for s, block in zip(metadata['sheets'], used['valueRanges']):
            p = s['properties']
            col_count = p['gridProperties']['columnCount']
            n, letters = col_count, ''
            while n:
                n, rem = divmod(n-1, 26)
                letters = chr(65+rem) + letters
            last = min(p['gridProperties']['rowCount'], len(block.get('values', [])) + 3)
            data_ranges.append(f"'{p['title']}'!A1:{letters}{max(1,last)}")
        return Snapshot(self.get(self.base, [('ranges', r) for r in data_ranges] + [
            ('includeGridData', 'true'),
            ('fields', 'spreadsheetId,properties,sheets(properties,data(startRow,startColumn,rowData(values(' + FIELDS + '))))')]))

    def write(self, requests):
        # Do not retry an ambiguous write. The caller re-reads after every response
        # or transport failure and reports uncertainty instead of double-writing.
        response = self.session.post(self.base + ':batchUpdate', json={'requests': requests}, timeout=(10, 45))
        if not response.ok:
            raise RuntimeError(f'Sheets write failed (HTTP {response.status_code})')
        return response.json()
