"""Opt-in one-post pilot. Persist intent before sending; never retry mutations."""
import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

import stvv_post as posting
from single_card import render, validate
from PIL import Image as PILImage

MANIFEST = Path('editorial/first_verified_card.json')
IMAGE = Path('generated/first_verified_card.png')
REPORT = Path('reports/single-card-pilot.json')


def write_report(value):
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def prepare_image(data):
    """Use approved raster bytes verbatim; never replace them with a redraw."""
    if 'asset_path' not in data:
        return render(data, IMAGE)
    path = Path(data['asset_path'])
    if path.parent != Path('generated') or path.suffix not in {'.jpg', '.png'}:
        raise ValueError('Approved image must be a generated JPEG or PNG')
    if hashlib.sha256(path.read_bytes()).hexdigest() != data.get('asset_sha256'):
        raise ValueError('Approved asset digest mismatch; no post sent')
    with PILImage.open(path) as image:
        if list(image.size) != data.get('asset_dimensions'):
            raise ValueError('Approved image dimensions differ')
        image.verify()
    return path


def main(publish=False):
    data = validate(json.loads(MANIFEST.read_text()))
    if posting.x_length(data['text']) > 270:
        raise ValueError('Caption exceeds X safety limit')
    image_path = prepare_image(data)
    if not publish:
        print('RENDER_OK: no Buffer request sent')
        return
    history = posting.load()
    if data['key'] in history['used_posts'] or data['key'] in history['pending_posts']:
        print('ALREADY_SUBMITTED_OR_PENDING: no duplicate sent')
        return
    # Publish the PNG first. No fallback to a different card or text-only post.
    posting.git('config', 'user.name', 'github-actions[bot]')
    posting.git('config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
    posting.git('add', '--', str(image_path))
    changed = subprocess.run(['git', 'diff', '--cached', '--quiet']).returncode
    if changed == 1:
        posting.git('commit', '-m', 'Render one verified STVV editorial pilot card')
        posting.git('push', 'origin', 'HEAD:main')
    elif changed != 0:
        raise RuntimeError('Cannot check image commit')
    rev = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    url = f'https://raw.githubusercontent.com/stvvlab/stvv-lab-auto-post/{rev}/{image_path}'
    remote = posting.SESSION.get(url, timeout=30)
    remote.raise_for_status()
    if hashlib.sha256(remote.content).digest() != hashlib.sha256(image_path.read_bytes()).digest():
        raise RuntimeError('Public PNG mismatch; no post sent')
    posting.publish(history, data['key'], data['text'], 'recap',
                    source=data['source_url'], image_url=url)
    item = next(p for p in history['publication_log'] if p['key'] == data['key'])
    result = {'key': data['key'], 'image_url': url,
              'buffer_id': item['buffer_id'], 'buffer_status': item['buffer_status'],
              'x_display_verified': False, 'x_url': None}
    write_report(result)
    # Read-only status polling; unknown outcome never triggers a second createPost.
    import os
    for attempt in range(6):
        response = posting.SESSION.post(posting.BUFFER, timeout=25,
            headers={'Authorization': 'Bearer ' + os.environ['BUFFER_API_KEY']},
            json={'query': 'query { post(input: { id: '+ json.dumps(item['buffer_id']) +
                  ' }) { id status } }'})
        response.raise_for_status()
        payload = response.json()
        if payload.get('errors'):
            result['status_query_error'] = payload['errors']
            break
        status = (payload.get('data', {}).get('post') or {}).get('status')
        result['buffer_status'] = status
        write_report(result)
        if str(status).lower() in {'sent', 'failed', 'error'}:
            break
        if attempt < 5:
            time.sleep(8)
    write_report(result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--publish', action='store_true')
    main(parser.parse_args().publish)
