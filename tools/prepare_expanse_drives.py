"""Translate reviewed source main-drive positions to the imported gameplay axes."""
import json
from pathlib import Path
import re
import numpy as np
from create_expanse_project import ROOT, GAMEPLAY_ENVELOPE
from expanse_axes import source_to_native


def main():
    for metadata_path in (ROOT / 'obj/expanse-authoring').glob('*/prepared.json'):
        metadata = json.loads(metadata_path.read_text())
        ident = metadata['workshop_id']
        folder = metadata_path.parent
        lower, upper = None, None
        for geometry in metadata['geometry']:
            with np.load(folder / geometry['prepared_geometry']) as archive:
                for section in range(int(archive['mesh_count'])):
                    points = archive[str(section) + '_positions'] * metadata['unit_metres']
                    lower = points.min(0) if lower is None else np.minimum(lower, points.min(0))
                    upper = points.max(0) if upper is None else np.maximum(upper, points.max(0))
        scale = GAMEPLAY_ENVELOPE[ident] / float(max(upper - lower))
        cfg = (folder / metadata['config']).read_text(encoding='utf-8-sig')
        positions = []
        candidates = [(name, body) for name, body in re.findall(r'EngineEffect\s+"([^"]+)"\s*\{(.*?)\}', cfg, re.S)
                      if re.search(r'Group\s+"Main"', body)]
        spheres = [(name, body) for name, body in candidates if re.search(r'Type\s+"Sphere"', body)]
        candidates = spheres or [(name, body) for name, body in candidates if not re.search(r'Wide|Extended', name, re.I)]
        hover = ident == '2375181309' and not candidates
        if hover:
            candidates = [(name, body) for name, body in re.findall(r'EngineEffect\s+"([^"]+)"\s*\{(.*?)\}', cfg, re.S)
                          if name.startswith('Large Thruster') and re.search(r'Group\s+"Hover"', body)]
        for name, body in candidates:
            match = re.search(r'Pos\s*\(([^)]+)\)', body)
            if not match:
                continue
            point = source_to_native([float(value) for value in match.group(1).split()], ident) * scale
            value = [round(float(axis), 5) for axis in point]
            if hover:
                # The shuttle's large jets are under the hull, unlike an aft
                # Epstein drive. Pitch the native aft-emitting particle down.
                value.extend([90, 0, 0])
            if value not in positions:
                positions.append(value)
        (folder / 'drive-positions.json').write_text(json.dumps(positions, indent=2) + '\n')
        print(metadata['display_name'], len(positions), 'distinct reviewed main-drive positions')


if __name__ == '__main__':
    main()
