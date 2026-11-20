"""Review: python tools/sync_makichika.py --source obj/reference-server
Import reviewed revision: add --apply. Network fetch is a separate explicit step.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://github.com/Makichika/Fractured-space-fixe-'

def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    source = args.source.resolve()
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    files = sorted((source / 'Space').rglob('*'))
    entries = []
    for file in files:
        if not file.is_file():
            continue
        rel = file.relative_to(source / 'Space').as_posix()
        data = file.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        target = ROOT / 'patch' / file.name
        print(('unchanged' if target.exists() and target.read_bytes() == data else 'UPDATE'), rel, sha)
        entries.append({'source': file.relative_to(source).as_posix(), 'file': file.name, 'destination': rel, 'sha256': sha})
    if len({e['file'] for e in entries}) != len(entries):
        raise SystemExit('Duplicate resource names: review mapping before importing')
    if not args.apply:
        return
    for entry in entries:
        (ROOT / 'patch' / entry['file']).write_bytes((source / entry['source']).read_bytes())
    # Update both platform manifests together, preserving offline-only resources.
    cs = ROOT / 'src/Installer/Installer.cs'
    py = ROOT / 'linux/fso_linux.py'
    ctext, ptext = cs.read_text(encoding='utf-8'), py.read_text(encoding='utf-8')
    for entry in entries:
        name, dest, sha = entry['file'], entry['destination'], entry['sha256']
        c_line = '        new PatchFile("%s", @"%s", "%s", false),' % (name, dest.replace('/', '\\'), sha)
        p_line = '    (%s, %s, %s),' % (json.dumps(name), json.dumps(dest), json.dumps(sha))
        crx = r'^        new PatchFile\("' + re.escape(name) + r'",.*$'
        prx = r'^    \("' + re.escape(name) + r'",.*$'
        if re.search(crx, ctext, re.M):
            ctext = re.sub(crx, lambda _: c_line, ctext, flags=re.M)
        else:
            ctext = ctext.replace('    public static readonly PatchFile[] Patch = new[]\n    {', '    public static readonly PatchFile[] Patch = new[]\n    {\n' + c_line)
        if re.search(prx, ptext, re.M):
            ptext = re.sub(prx, lambda _: p_line, ptext, flags=re.M)
        else:
            ptext = ptext.replace('PATCH = [', 'PATCH = [\n' + p_line)
    cs.write_text(ctext, encoding='utf-8')
    py.write_text(ptext, encoding='utf-8')
    (ROOT / 'tools/makichika-lock.json').write_text(json.dumps({'repository': URL, 'revision': revision, 'files': entries}, indent=2) + '\n')

if __name__ == '__main__':
    main()
