"""Prepare reviewed source geometry/materials locally; never install raw SM files.

python tools/prepare_expanse.py --ship 2211361535
Outputs remain under ignored obj/expanse-authoring. No audio is copied.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile
from audit_expanse import PACKS
from expanse_sm import read_sm, save_npz

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {'.cfg', '.sss', '.sml', '.mtl', '.png', '.jpg', '.jpeg', '.dds', '.tga'}

def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--ship', choices=list(PACKS), action='append')
    parser.add_argument('--workshop-root', type=Path, default=Path('C:/Program Files (x86)/Steam/steamapps/workshop/content/314650'))
    args = parser.parse_args()
    lock = json.loads((ROOT / 'mods/expanse/source-manifest.json').read_text(encoding='utf-8'))
    records = {entry['workshop_id']: entry for entry in lock['ships']}
    for ident in args.ship or PACKS:
        record = records[ident]
        source = args.workshop_root / ident
        for entry in record['files']:
            path = source / entry['path']
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
                raise SystemExit('Source differs from the reviewed inventory: ' + str(path))
        output = ROOT / 'obj/expanse-authoring' / ident
        staging = output / 'source'
        staging.mkdir(parents=True, exist_ok=True)
        models = []
        for file in sorted(source.rglob('*')):
            if not file.is_file():
                continue
            rel = file.relative_to(source)
            if file.suffix.lower() in ALLOWED:
                dest = staging / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(file, dest)
            elif file.suffix.lower() == '.pak':
                if not zipfile.is_zipfile(file):
                    raise ValueError('Expected a SpaceEngine ZIP PAK: ' + str(file))
                with zipfile.ZipFile(file) as archive:
                    for item in archive.infolist():
                        if item.is_dir():
                            continue
                        suffix = Path(item.filename).suffix.lower()
                        dest = (staging / item.filename).resolve()
                        if not dest.is_relative_to(staging.resolve()):
                            raise ValueError('Unsafe archive entry')
                        if suffix == '.sm':
                            models.append((item.filename, archive.read(item)))
                        elif suffix in ALLOWED:
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            dest.write_bytes(archive.read(item))
        if len(models) != len(record['meshes']):
            raise ValueError('The preparation pipeline has not accounted for all reviewed meshes')
        reports = []
        for index, (name, data) in enumerate(models):
            meshes = read_sm(data)
            geometry = output / ('geometry-%d.npz' % index)
            save_npz(meshes, geometry)
            reports.append({'source_mesh': name, 'prepared_geometry': geometry.name,
                            'mesh_sections': len(meshes), 'triangles': sum(len(m.triangles) for m in meshes),
                            'repaired_normals': sum(m.repaired_normals for m in meshes),
                            'degenerate_triangles_removed': sum(m.degenerate_triangles_removed for m in meshes)})
        configs = [p for p in staging.rglob('*.cfg') if re.search(r'^\s*Mesh\s+', p.read_text(encoding='utf-8-sig', errors='replace'), re.M)]
        if len(configs) != len(models):
            raise ValueError('Resolve module/config mappings before preparing this package')
        config_text = configs[0].read_text(encoding='utf-8-sig', errors='replace')
        unit_match = re.search(r'^\s*Unit\s+([0-9.eE+-]+)', config_text, re.M)
        metadata = {'workshop_id': ident, 'display_name': record['planned_ingame_display_name'],
                    'source_credit': record['model_texture_credit'], 'source_url': record['source_url'],
                    'license': record['declared_graphics_license'], 'release_ready': False,
                    'config': configs[0].relative_to(output).as_posix(),
                    'unit_metres': float(unit_match.group(1)) if unit_match else 1.0,
                    'materials': re.findall(r'^\s*Material\s+"([^"]+)"', config_text, re.M),
                    'geometry': reports, 'requires_visual_validation': True,
                    'audio_included': False,
                    'yacht_texture_restriction': ident == '2368610280'}
        (output / 'prepared.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8', newline='\n')
        print(metadata['display_name'], reports, flush=True)

if __name__ == '__main__':
    main()
