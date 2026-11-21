"""Keep native damage/audio callbacks without stock-hull vernier geometry.

Damage particles are localized to six actual surface intersections. Their
original baked cylinder/sphere spawn volumes belong to vanilla hulls and must
not be carried across to the imported ships.
"""
import base64
import copy
import json
import sys
from pathlib import Path
import numpy as np
import build_rocinante_pdc as assets
from create_expanse_project import GAMEPLAY_ENVELOPE
from expanse_axes import source_to_native
from read_game_pak import Pak

ROOT = assets.ROOT
AUTHOR = ROOT / 'obj/expanse-authoring'
CONTENT = AUTHOR / 'patch-content/Content'
GAME = Path('C:/Program Files (x86)/Steam/steamapps/common/Space/spacegame/Content/Paks')


def set_property(asset, data, name, value, kind='Bool'):
    existing = next((p for p in data if p['Name'] == name), None)
    if existing is None:
        assets.names(asset, name, kind + 'Property')
        existing = {'$type': 'UAssetAPI.PropertyTypes.Objects.' + kind + 'PropertyData, UAssetAPI',
                    'Name': name, 'ArrayIndex': 0, 'Value': value}
        data.append(existing)
    existing['Value'] = value


def set_vector(asset, data, name, point):
    existing = next((p for p in data if p['Name'] == name), None)
    if existing is None:
        assets.names(asset, name, 'Vector', 'StructProperty')
        existing = {'$type': 'UAssetAPI.PropertyTypes.Structs.StructPropertyData, UAssetAPI',
            'Name': name, 'StructType': 'Vector', 'SerializeNone': True, 'ArrayIndex': 0,
            'Value': [{'$type': 'UAssetAPI.PropertyTypes.Structs.VectorPropertyData, UAssetAPI',
                       'Name': name, 'Value': dict(zip(('X', 'Y', 'Z'), map(float, point)))}]}
        data.append(existing)
    else:
        assets.vector(existing, point)


def surface_points(spec):
    folder = AUTHOR / spec['workshop_id']
    metadata = json.loads((folder / 'prepared.json').read_text())
    sections = []
    for geometry in metadata['geometry']:
        with np.load(folder / geometry['prepared_geometry']) as archive:
            for i in range(int(archive['mesh_count'])):
                points = archive[str(i) + '_positions'] * metadata['unit_metres']
                sections.append(points.reshape(-1, 3, 3))
    triangles = source_to_native(np.concatenate(sections), spec['workshop_id'])
    points = triangles.reshape(-1, 3)
    scale = GAMEPLAY_ENVELOPE[spec['workshop_id']] / np.ptp(points, axis=0).max()
    triangles *= scale
    result = {}
    for region, axis, sign in [('Front', 0, 1), ('Back', 0, -1), ('Left', 1, -1),
                                ('Right', 1, 1), ('Top', 2, 1), ('Bottom', 2, -1)]:
        other = [i for i in range(3) if i != axis]
        projected = triangles[:, :, other]
        mask = np.all(projected.min(1) <= 0, axis=1) & np.all(projected.max(1) >= 0, axis=1)
        candidates = triangles[mask]
        p = candidates[:, :, other]
        a, b = p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]
        det = a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]
        valid = abs(det) > 1e-10
        p, a, b, candidates, det = p[valid], a[valid], b[valid], candidates[valid], det[valid]
        u = (-p[:, 0, 0] * b[:, 1] + p[:, 0, 1] * b[:, 0]) / det
        v = (-a[:, 0] * p[:, 0, 1] + a[:, 1] * p[:, 0, 0]) / det
        valid = (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1 + 1e-6)
        hits = candidates[:, 0, axis] + u * (candidates[:, 1, axis] - candidates[:, 0, axis]) + v * (candidates[:, 2, axis] - candidates[:, 0, axis])
        hits = hits[valid]
        if not len(hits):
            raise ValueError('No hull surface intersection: ' + spec['slug'] + '/' + region)
        point = np.zeros(3)
        point[axis] = sign * (max(hits * sign) - 0.25)
        result[region] = point.tolist()
    return result


def normalize_distribution(value, number):
    if isinstance(value, dict):
        if value.get('Name') == 'Distribution' and 'ObjectPropertyData' in value.get('$type', ''):
            value['Value'] = 0
        elif 'FloatPropertyData' in value.get('$type', ''):
            value['Value'] = number
        elif 'VectorPropertyData' in value.get('$type', ''):
            value['Value'] = dict.fromkeys(('X', 'Y', 'Z'), number)
        for child in value.values():
            normalize_distribution(child, number)
    elif isinstance(value, list):
        for child in value:
            normalize_distribution(child, number)


def main():
    assets.WORK = AUTHOR / 'effects-work'
    assets.WORK.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT / 'obj/tooling/python'))
    key = base64.b64decode(json.loads((ROOT / 'obj/expanse-review/local-content-crypto.json').read_text())['EncryptionKey']['Key'])
    packs = {'Blueprints': Pak(GAME / 'BP.pak', key), 'Particles': Pak(GAME / 'PA.pak', key)}

    def extract(package):
        group, relative = package.removeprefix('/Game/').split('/', 1)
        destination = assets.WORK / 'source' / group / relative
        for suffix in ('.uasset', '.uexp'):
            entry = relative + suffix
            if entry in packs[group].entries:
                target = destination.with_suffix(suffix)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(packs[group].read(entry))
        return destination.with_suffix('.uasset')

    report = {}
    for spec in json.loads((ROOT / 'mods/expanse/fleet.json').read_text()):
        title = ''.join(p.title() for p in spec['slug'].split('_'))
        source_ship = json.loads((ROOT / 'obj/expanse-review/game-SD' / spec['archetype_ship']).read_text())
        system_path = next(p.split('.')[0] for n in source_ship['nodes'] if n['name'] == 'Hull'
                           for p in n['maSystems'] if '/BP_FX_SYS_' in p)
        system = assets.dump(extract(system_path), title + '-system')
        part_path = next(i['ObjectName'] for i in system['Imports']
                         if i['ClassName'] == 'Package' and '/BP_FX_PRT_' in i['ObjectName'])
        part = assets.dump(extract(part_path), title + '-part')
        new_system = '/Game/Blueprints/Systems/Expanse/BP_FX_EXP_' + title
        new_part = '/Game/Blueprints/Parts/Expanse/BP_FX_PRT_EXP_' + title
        system = assets.replace(system, [(system_path, new_system), (system_path.split('/')[-1], new_system.split('/')[-1]),
                                         (part_path, new_part), (part_path.split('/')[-1], new_part.split('/')[-1])])
        part = assets.replace(part, [(part_path, new_part), (part_path.split('/')[-1], new_part.split('/')[-1])])
        surfaces = surface_points(spec)
        templates = {}
        for imp in part['Imports']:
            old = imp['ObjectName']
            if imp['ClassName'] != 'Package' or '/DestroyedArmour/' not in old:
                continue
            region = next((r for r in surfaces if old.lower().endswith(r.lower())), None)
            if region is None:
                raise ValueError('Unmapped damage effect: ' + old)
            particle = assets.dump(extract(old), title + '-' + region)
            new = '/Game/Expanse/Effects/' + title + '/P_Damage_' + title + '_' + region
            particle = assets.replace(particle, [(old, new), (old.split('/')[-1], new.split('/')[-1])])
            modules = 0
            for export in particle['Exports']:
                if not isinstance(export.get('Data'), list):
                    continue
                if export['ObjectName'].startswith('ParticleModuleLocationPrimitive'):
                    modules += 1
                    for prop in export['Data']:
                        if prop['Name'] in ('StartRadius', 'StartHeight', 'StartLocation'):
                            normalize_distribution(prop, 0.5 if prop['Name'] != 'StartLocation' else 0.0)
                if export['ObjectName'] == new.split('/')[-1]:
                    set_property(particle, export['Data'], 'bUseFixedRelativeBoundingBox', False)
            if not modules:
                raise ValueError('Damage spawn volume needs review: ' + old)
            assets.write(particle, CONTENT / (new.removeprefix('/Game/') + '.uasset'))
            templates[old] = (new, region)
        disabled = []
        for export in part['Exports']:
            data = export.get('Data')
            if not isinstance(data, list):
                continue
            mesh = next((p for p in data if p['Name'] == 'StaticMesh'), None)
            if mesh:
                mesh['Value'] = 0
                for name, value in [('bVisible', False), ('bHiddenInGame', True), ('CastShadow', False)]:
                    set_property(part, data, name, value)
                disabled.append(export['ObjectName'])
            template = next((p for p in data if p['Name'] == 'Template' and p['Value'] < 0), None)
            if template:
                imp = part['Imports'][-template['Value'] - 1]
                package = part['Imports'][-imp['OuterIndex'] - 1]['ObjectName']
                if package in templates:
                    region = templates[package][1]
                    set_vector(part, data, 'RelativeLocation', surfaces[region])
                    # A localized flame must not retain an archetype scale.
                    size = min(1.0, GAMEPLAY_ENVELOPE[spec['workshop_id']] / 600)
                    set_vector(part, data, 'RelativeScale3D', (size, size, size))
        pairs = []
        for old, (new, _) in templates.items():
            pairs.extend([(old, new), (old.split('/')[-1], new.split('/')[-1])])
        part = assets.replace(part, pairs)
        assets.write(system, CONTENT / (new_system.removeprefix('/Game/') + '.uasset'))
        assets.write(part, CONTENT / (new_part.removeprefix('/Game/') + '.uasset'))
        report[title] = {'removed_stock_meshes': disabled, 'damage_surfaces': surfaces}
        print('Adapted native hull effects:', title, flush=True)
    (AUTHOR / 'effects-validation.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
