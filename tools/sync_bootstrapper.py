"""Review a published bootstrapper patch ZIP; --apply imports verified payloads.

Use a published release rather than treating experimental source patches as
released. Preserve offline-specific scripts and record that deliberate choice.
Never imports the bootstrapper application directory or account recordings.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PRESERVE = {'startgame-script.js': 'Preserve offline server ordering.',
            'results-script.js': 'Preserve live personal match-result recording.'}
RETIRED = ['Makichika_MapJamming_P.pak', 'Makichika_ProtectorShield_P.pak', 'Makichika_VenturerSkins_P.pak']


def update_manifest(file, name, destination, sha, remove=False):
    text = file.read_text(encoding='utf-8')
    if file.suffix == '.cs':
        pattern = r'^        new PatchFile\("' + re.escape(name) + r'",.*\n?'
        line = '        new PatchFile("%s", @"%s", "%s", false),\n' % (name, destination.replace('/', '\\'), sha)
        anchor = '    public static readonly PatchFile[] Patch = new[]\n    {\n'
    else:
        pattern = r'^    \("' + re.escape(name) + r'",.*\n?'
        line = '    (%s, %s, %s),\n' % tuple(json.dumps(v) for v in (name, destination, sha))
        anchor = 'PATCH = [\n'
    if re.search(pattern, text, re.M):
        text = re.sub(pattern, lambda _: '' if remove else line, text, flags=re.M)
    elif not remove:
        if anchor not in text:
            raise ValueError('Could not locate platform manifest: ' + str(file))
        text = text.replace(anchor, anchor + line, 1)
    file.write_text(text, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--zip', type=Path, required=True)
    parser.add_argument('--release', required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    manifests = [ROOT / 'src/Installer/Installer.cs', ROOT / 'linux/fso_linux.py']
    entries = []
    with zipfile.ZipFile(args.zip) as archive:
        sums = archive.read('SHA256SUMS.txt').decode('utf-8')
        level = json.loads(archive.read('bootlegger.json'))['version']
        payloads = []
        for line in sums.splitlines():
            expected, destination = line.split('  ', 1)
            path = Path(destination)
            if path.is_absolute() or '..' in path.parts or not destination.startswith(('spacegame/', 'Engine/Config/')):
                raise ValueError('Unexpected published payload destination')
            data = archive.read(destination)
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError('Published payload hash mismatch: ' + destination)
            name = path.name
            if name in {p[0] for p in payloads}:
                raise ValueError('Resource filename collision: ' + name)
            if name in PRESERVE:
                data = (ROOT / 'patch' / name).read_bytes()
            final = hashlib.sha256(data).hexdigest()
            entries.append({'file': name, 'destination': destination, 'upstream_sha256': expected,
                            'sha256': final, 'adaptation': PRESERVE.get(name, 'Published payload, unchanged.')})
            payloads.append((name, destination, data, final))
            print(name, 'preserved offline adaptation' if name in PRESERVE else 'published release payload')
    if not args.apply:
        return
    for name, destination, data, sha in payloads:
        (ROOT / 'patch' / name).write_bytes(data)
        for manifest in manifests:
            update_manifest(manifest, name, destination, sha)
    for name in RETIRED:
        for manifest in manifests:
            update_manifest(manifest, name, '', '', remove=True)
    lock = {'repository': 'https://github.com/Tigerhacker/fractured-bootstrapper',
            'release': args.release, 'revision': args.revision, 'patch_level': level,
            'archive_sha256': hashlib.sha256(args.zip.read_bytes()).hexdigest(),
            'files': entries, 'retired_overlays': RETIRED,
            'note': 'Release v2.0.1 includes the five fixes still marked testing in the tagged source. The published ZIP is authoritative for this integration.'}
    (ROOT / 'tools/bootstrapper-lock.json').write_bytes((json.dumps(lock, indent=2) + '\n').encode('utf-8'))


if __name__ == '__main__':
    main()
