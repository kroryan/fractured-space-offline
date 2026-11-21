"""Reassemble the cooked test PAK from Git-sized, hash-checked binary parts."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'mods/expanse/payload'


def restore():
    index = json.loads((BUNDLE / 'pak-parts.json').read_text())
    destination = BUNDLE / index['filename']
    if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() == index['sha256']:
        return
    temporary = destination.with_suffix('.assembling')
    digest = hashlib.sha256()
    try:
        with temporary.open('wb') as out:
            for part in index['parts']:
                source = BUNDLE / part['name']
                if source.parent != BUNDLE or source.name != part['name']:
                    raise ValueError('Invalid payload part path')
                data = source.read_bytes()
                if hashlib.sha256(data).hexdigest() != part['sha256']:
                    raise ValueError('Payload part hash mismatch: ' + source.name)
                digest.update(data)
                out.write(data)
        if digest.hexdigest() != index['sha256']:
            raise ValueError('Reassembled PAK hash mismatch')
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    print('Restored and verified cooked Expanse PAK.')


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--split', type=Path, help='Maintainer: refresh binary parts from the packaged PAK')
    args = parser.parse_args()
    if args.split:
        data = args.split.read_bytes()
        index = {'filename': args.split.name, 'sha256': hashlib.sha256(data).hexdigest(), 'parts': []}
        size = 80 * 1024 * 1024
        for number, start in enumerate(range(0, len(data), size)):
            block = data[start:start + size]
            name = args.split.name + '.part' + str(number).zfill(3)
            (BUNDLE / name).write_bytes(block)
            index['parts'].append({'name': name, 'sha256': hashlib.sha256(block).hexdigest()})
        (BUNDLE / 'pak-parts.json').write_text(json.dumps(index, indent=2) + '\n', encoding='utf-8')
        print('Created', len(index['parts']), 'hash-checked binary parts.')
    else:
        restore()


if __name__ == '__main__':
    main()
