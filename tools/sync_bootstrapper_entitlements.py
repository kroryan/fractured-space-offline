"""Import only offline entitlement routes from reviewed official recordings.

Account identity, progression, statistics and all unrelated responses stay local.
The runtime still rewrites recorded identity per local player.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def entitlement(entry):
    path = urlsplit(entry['request']['url']).path
    return path.endswith('/licenses') or path == '/licenses/bundle/check'


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    upstream = json.loads(args.source.read_text(encoding='utf-8'))
    target = ROOT / 'server/responses.json'
    local = json.loads(target.read_text(encoding='utf-8'))
    selected = [e for e in upstream if entitlement(e)]
    if len(selected) != 3:
        raise ValueError('Unexpected entitlement route inventory; review before import.')
    pending = iter(selected[:2])
    updated = [copy.deepcopy(next(pending)) if urlsplit(e['request']['url']).path.endswith('/licenses') else e for e in local]
    if not any(urlsplit(e['request']['url']).path == '/licenses/bundle/check' for e in local):
        updated.append(copy.deepcopy(selected[2]))
    else:
        updated = [copy.deepcopy(selected[2]) if urlsplit(e['request']['url']).path == '/licenses/bundle/check' else e for e in updated]
    print('Reviewed entitlement routes:', len(selected), '; unrelated responses preserved.')
    if args.apply:
        target.write_bytes((json.dumps(updated, indent=2) + '\n').encode('utf-8'))
        lock_path = ROOT / 'tools/bootstrapper-lock.json'
        lock = json.loads(lock_path.read_text(encoding='utf-8'))
        lock['entitlements'] = {'source': 'Official v2.0.1 Debian package resources/data/fireline-responses.json',
            'source_sha256': hashlib.sha256(args.source.read_bytes()).hexdigest(),
            'routes': [urlsplit(e['request']['url']).path for e in selected],
            'policy': 'Only license/bundle routes imported; profile, statistics, crew XP and identity rewriting preserved.'}
        lock_path.write_bytes((json.dumps(lock, indent=2) + '\n').encode('utf-8'))


if __name__ == '__main__':
    main()
