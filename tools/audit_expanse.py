"""Inventory every ship definition, including definitions inside ZIP-based SpaceEngine PAKs.

python tools/audit_expanse.py --output mods/expanse/source-manifest.json
This audits source assets only; it does not install or register playable Unreal ships.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

PACKS = {
    '2211361535': ('MCRN Tachi', 'Anton Perfilev (wintermute666)', 'jamesmule', 'CC-BY-NC-SA-4.0', 'https://creativecommons.org/licenses/by-nc-sa/4.0/'),
    '2224316655': ('Razorback', 'Chris Kuhn; CC0Textures.com', 'jamesmule; retro-visor', 'CC0-1.0', 'https://creativecommons.org/publicdomain/zero/1.0/'),
    '2375119898': ('MCRN Donnager', 'Chris Kuhn; model distributed by strawfinch', 'jamesmule; retro-visor', 'CC0-1.0', 'https://creativecommons.org/publicdomain/zero/1.0/'),
    '2687045417': ('UNN Mayotte', 'Azzecco (lux_comodo)', 'jamesmule', 'CC-BY-NC-4.0', 'https://creativecommons.org/licenses/by-nc/4.0/'),
    '2687094193': ('MCRN Avalanche', 'Azzecco (lux_comodo)', 'jamesmule', 'CC-BY-NC-4.0', 'https://creativecommons.org/licenses/by-nc/4.0/'),
    '2368610280': ("Epstein's Yacht", 'Chris Kun (as credited by the source); strawfinch', 'retro-visor', 'REQUIRES-VERIFICATION', None),
}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def inspect_definition(path, data):
    text = data.decode('utf-8-sig', 'replace')
    name = re.search(r'^\s*Name\s+"([^"]+)"', text, re.M)
    return {'path': path, 'name': name.group(1) if name else None, 'sha256': digest(data)}

def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--workshop-root', type=Path, default=Path('C:/Program Files (x86)/Steam/steamapps/workshop/content/314650'))
    parser.add_argument('--output', type=Path, default=Path('obj/expanse-source-manifest.json'))
    args = parser.parse_args()
    records = []
    for ident, (title, artist, adapter, license_id, license_url) in PACKS.items():
        root = args.workshop_root / ident
        files, ships, meshes = [], [], []
        for path in sorted(root.rglob('*')):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            data = path.read_bytes()
            files.append({'path': rel, 'bytes': len(data), 'sha256': digest(data)})
            if path.suffix.lower() == '.sss':
                ships.append(inspect_definition(rel, data))
            if path.suffix.lower() == '.sm':
                meshes.append({'path': rel, 'format': data[:4].decode('ascii', 'replace'), 'bytes': len(data)})
            if path.suffix.lower() == '.pak' and zipfile.is_zipfile(path):
                with zipfile.ZipFile(path) as archive:
                    for item in archive.infolist():
                        if item.filename.lower().endswith('.sss'):
                            ships.append(inspect_definition(rel + '::' + item.filename, archive.read(item)))
                        elif item.filename.lower().endswith('.sm'):
                            with archive.open(item) as stream:
                                header = stream.read(4)
                            meshes.append({'path': rel + '::' + item.filename, 'format': header.decode('ascii', 'replace'), 'bytes': item.file_size})
        if not files:
            raise SystemExit('Workshop item is missing or not downloaded: ' + ident)
        records.append({'workshop_id': ident, 'title': title,
                        'source_url': 'https://steamcommunity.com/sharedfiles/filedetails/?id=' + ident,
                        'model_texture_credit': artist, 'spaceengine_adapter_credit': adapter,
                        'declared_graphics_license': license_id, 'license_url': license_url,
                        'playable_in_fractured_space': False, 'default_account_ownership_when_integrated': True,
                        'ship_definitions': ships, 'meshes': meshes, 'files': files})
        print(title, ':', len(ships), 'ship definitions,', len(meshes), 'meshes')
    report = {'schema': 1, 'status': 'source-audit-only', 'ships': records,
              'audio_policy': 'Do not redistribute show-derived audio based on a model license.',
              'integration_requirements': ['Resolve per-asset redistribution rights', 'Convert SM02 geometry/materials',
                                           'Author and cook compatible Unreal 4.19.2 assets',
                                           'Register client/server ship definitions and default-account ownership',
                                           'Verify hangar selection, spawning and gameplay before release']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')

if __name__ == '__main__':
    main()
