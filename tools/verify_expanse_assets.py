"""Validate actual cooked meshes, muzzle sockets and generated weapon bindings.

These checks catch authoring/packaging regressions. They do not simulate combat
or establish that turret aiming, firing and damage work in a live client.
"""
import json
import math
from pathlib import Path
import subprocess
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
AUTHOR = ROOT / 'obj/expanse-authoring'
COOKED = AUTHOR / 'UnrealProject/Saved/Cooked/WindowsNoEditor/spacegame/Content/Expanse'
BLUEPRINTS = AUTHOR / 'patch-content/Content/Blueprints'
TOOL = [str(ROOT / 'obj/tooling/dotnet/dotnet.exe'),
        str(ROOT / 'tools/FleetAssetTool/bin/Debug/net10.0/FleetAssetTool.dll')]
OUT = AUTHOR / 'asset-checks'


def properties(export):
    return {item['Name']: item for item in export.get('Data', [])} if isinstance(export.get('Data'), list) else {}


def dump(path):
    destination = OUT / (path.stem + '.json')
    subprocess.run(TOOL + ['dump', str(path), str(destination)], check=True, capture_output=True, text=True)
    return json.loads(destination.read_text())


def vector(item):
    value = item['Value'][0]['Value']
    return np.array([float(value[axis]) for axis in ('X', 'Y', 'Z')])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    expected = {'Rocinante': ('Rocinante', 6, 1), 'Avalanche': ('MCRN_Avalanche', 2, 1),
        'Mayotte': ('UNN_Mayotte', 44, 6), 'Donnager': ('MCRN_Donnager', 2, 4),
        'Chariot': ('MCRN_Chariot_Type_Dropship', 2, 4), 'Razorback': ('Razorback', 1, 1),
        'EpsteinYacht': ('Epstein_s_Yacht', 0, 1)}
    report = {'ships': {}, 'weapon_meshes': {}, 'gameplay_validated': False}
    for title, (folder, ballistic_expected, engines_expected) in expected.items():
        meshes = []
        for name in (folder, 'SM_ARM_EXP_' + folder):
            info = json.loads(subprocess.check_output(TOOL + ['mesh-info', str(COOKED / folder / (name + '.uasset'))], text=True))
            meshes.append(info)
        if meshes[1]['material_count'] != 6:
            raise ValueError(title + ': armour does not have six native damage regions')
        for key in ('Origin', 'BoxExtent'):
            np.testing.assert_allclose(meshes[0]['bounds'][key], meshes[1]['bounds'][key], atol=0.02,
                                       err_msg=title + ': armour and visual hull bounds differ')
        extent = meshes[0]['bounds']['BoxExtent']
        if not extent[0] > max(extent[1:]):
            raise ValueError(title + ': longest hull axis is not native X')
        hull = dump(BLUEPRINTS / ('Parts/Expanse/BP_SHP_EXP_' + title + '_01.uasset'))
        ballistic, missiles, engines = [], [], []
        for export in hull['Exports']:
            data = properties(export)
            if 'AllHardpointData' in data:
                for point in data['AllHardpointData']['Value']:
                    fields = {p['Name']: p for p in point['Value']}
                    kinds = [p['EnumValue'].rsplit('_', 1)[-1] for p in fields['TypesSupported']['Value']]
                    if 'Ballistic' in kinds:
                        ballistic.append(fields)
                    if 'Missile' in kinds:
                        missiles.append(fields)
                    socket = {p['Name']: p for p in fields['Socket']['Value']}
                    if socket['UsingSocket']['Value']:
                        raise ValueError(title + ': a mount still relies on a stock hull socket')
                    transform = {p['Name']: p for p in fields['Transform']['Value']}
                    rotation = transform['Rotation']['Value'][0]['Value']
                    norm = sum(float(rotation[k]) ** 2 for k in ('X', 'Y', 'Z', 'W'))
                    if abs(norm - 1) > 0.0001:
                        raise ValueError(title + ': invalid mount rotation')
            if export['ObjectName'].startswith('ThrusterParticle') and data.get('Template', {}).get('Value', 0):
                engines.append(vector(data['RelativeLocation']).tolist())
            if export['ObjectName'].startswith('SkinnedPointLight') and float(data.get('Intensity', {}).get('Value', 0)) != 0:
                raise ValueError(title + ': inherited stock point light remains enabled')
        if len(ballistic) != ballistic_expected or len(engines) != engines_expected:
            raise ValueError(f'{title}: mounts {len(ballistic)}/{ballistic_expected}; engines {len(engines)}/{engines_expected}')
        report['ships'][title] = {'ballistic_mounts': len(ballistic), 'missile_mounts': len(missiles),
                                  'main_nozzles': len(engines), 'armour_regions': 6}
        fx = dump(BLUEPRINTS / ('Parts/Expanse/BP_FX_PRT_EXP_' + title + '.uasset'))
        for export in fx['Exports']:
            data = properties(export)
            if data.get('StaticMesh', {}).get('Value', 0):
                raise ValueError(title + ': stock hull effects mesh remains active')
        effects = json.loads((AUTHOR / 'effects-validation.json').read_text())[title]
        if len(effects['damage_surfaces']) != 6 or not effects['removed_stock_meshes']:
            raise ValueError(title + ': missing adapted damage/vernier effects')
    for folder in COOKED.iterdir():
        if not folder.is_dir():
            continue
        for path in folder.glob('*_Gun.uasset'):
            if not path.name.startswith(('Cannon_', 'Railgun_', 'PDC_')):
                continue
            info = json.loads(subprocess.check_output(TOOL + ['mesh-info', str(path)], text=True))
            socket = next((s for s in info['sockets'] if s['name'] == 'Socket'), None)
            if socket is None or not all(math.isfinite(v) for v in socket['location']):
                raise ValueError('Missing native bore socket: ' + path.name)
            if any(abs(v) > 0.01 for v in socket['rotation']):
                raise ValueError('Bore socket does not point along the barrel: ' + path.name)
            origin, extent = np.array(info['bounds']['Origin']), np.array(info['bounds']['BoxExtent'])
            muzzle = np.array(socket['location'])
            if abs(muzzle[0] - (origin[0] + extent[0])) > 1.0:
                raise ValueError('Muzzle is not at the forward barrel tip: ' + path.name)
            if np.any(np.abs(muzzle[1:] - origin[1:]) > extent[1:] + 1):
                raise ValueError('Muzzle is outside its weapon geometry: ' + path.name)
            report['weapon_meshes'][path.stem] = {'bore_socket': muzzle.tolist(), 'material_count': info['material_count']}
    if len(report['weapon_meshes']) != 12:
        raise ValueError('Expected twelve distinct cooked gun meshes, found ' + str(len(report['weapon_meshes'])))
    systems = {'Rocinante_PDC': 6, 'Rocinante_Torpedoes': 2, 'Donnager_Railguns': 2, 'Donnager_Torpedoes': 6,
               'Mayotte_Railguns': 2, 'Mayotte_PDC': 42, 'Avalanche_Cannons': 2,
               'Chariot_Cannons': 2, 'Razorback_LightCannon': 1}
    report['weapon_systems'] = {}
    for name, concurrent in systems.items():
        asset = dump(BLUEPRINTS / ('Systems/Subsystems/Expanse/BP_SYS_EXP_' + name + '.uasset'))
        cdo = properties(next(e for e in asset['Exports'] if e['ObjectName'].startswith('Default__')))
        if cdo['MaxConcurrentTurrets']['Value'] != concurrent:
            raise ValueError('Unexpected concurrent firing limit: ' + name)
        report['weapon_systems'][name] = {'max_concurrent_turrets': concurrent,
                                          'part_types': len(cdo['SystemParts']['Value'])}
    (AUTHOR / 'asset-validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Verified 7 cooked hull/armour pairs, 12 bore sockets, source mount counts and native firing limits.')
    print('These checks do not validate live firing, articulation, damage or balance.')


if __name__ == '__main__':
    main()
