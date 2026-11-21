"""Bind source PDC meshes to native aiming components at the six source mounts.

All outputs remain in obj/. This replaces inherited stock cannon/CIWS mounts;
it does not approve inherited torpedo locations or other ships' weapon layouts.
"""
import copy
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
AUTHOR = ROOT / 'obj/expanse-authoring'
BASE = ROOT / 'obj/expanse-review/base-blueprints'
OUT = AUTHOR / 'patch-content/Content/Blueprints'
WORK = AUTHOR / '2211361535/pdc-assets'
DOTNET = ROOT / 'obj/tooling/dotnet/dotnet.exe'
TOOL = ROOT / 'tools/FleetAssetTool/bin/Debug/net10.0/FleetAssetTool.dll'


def call(*args):
    subprocess.run([str(DOTNET), str(TOOL), *map(str, args)], check=True)


def dump(source, name):
    path = WORK / (name + '.json')
    call('dump', source, path)
    return json.loads(path.read_text())


def replace(tree, pairs):
    if isinstance(tree, str):
        for before, after in pairs:
            tree = tree.replace(before, after)
        return tree
    if isinstance(tree, list):
        return [replace(value, pairs) for value in tree]
    if isinstance(tree, dict):
        return {key: replace(value, pairs) for key, value in tree.items()}
    return tree


def names(asset, *values):
    for value in values:
        match = re.match(r'^(.*)_([0-9]+)$', value)
        candidates = [value]
        if match and not (len(match[2]) > 1 and match[2].startswith('0')):
            candidates.append(match[1])
        for candidate in candidates:
            if candidate not in asset['NameMap']:
                asset['NameMap'].append(candidate)


def prop(data, name):
    return next(item for item in data if item['Name'] == name)


def vector(item, values):
    target = item['Value'][0]['Value']
    for key, value in zip(('X', 'Y', 'Z'), values):
        target[key] = value


def write(asset, destination):
    path = WORK / (destination.stem + '-edited.json')
    path.write_text(json.dumps(asset))
    call('write', path, destination)


def empty(array):
    if array['Value']:
        array['DummyStruct'] = copy.deepcopy(array['Value'][0])
    array['Value'] = []


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    rig = json.loads((AUTHOR / '2211361535/pdc-rig.json').read_text())
    turret = dump(BASE / 'Turrets/BP_Turret_Titan_03.uasset', 'native-turret')
    old = 'BP_Turret_Titan_03'
    for variant in ('Negative', 'Positive'):
        name = 'BP_Turret_Rocinante_' + variant
        asset = replace(turret, [
            ('/Game/Blueprints/Turrets/' + old, '/Game/Blueprints/Turrets/Expanse/' + name),
            (old, name),
            ('/Game/Meshes/Turrets/WM_00/TitanTurret/SM_TitanTurret_001_GUN', '/Game/Expanse/Rocinante/PDC_Rocinante_' + variant + '_Gun'),
            ('SM_TitanTurret_001_GUN', 'PDC_Rocinante_' + variant + '_Gun'),
            ('/Game/Meshes/Turrets/WM_00/TitanTurret/SM_TitanTurret_001_SWIVEL', '/Game/Expanse/Rocinante/PDC_Rocinante_' + variant + '_Swivel'),
            ('SM_TitanTurret_001_SWIVEL', 'PDC_Rocinante_' + variant + '_Swivel')])
        for export in asset['Exports']:
            if export['ObjectName'].startswith('Default__'):
                prop(export['Data'], 'bDontRotateSwivelMesh')['Value'] = False
                prop(export['Data'], 'YawSpeed')['Value'] = 180.0
                prop(export['Data'], 'PitchSpeed')['Value'] = 120.0
                prop(export['Data'], 'MinHardPitchLimit')['Value'] = -5.0
            if export['ObjectName'] == 'GunMesh0':
                vector(prop(export['Data'], 'RelativeLocation'), (0, 0, 0))
        write(asset, OUT / ('Turrets/Expanse/' + name + '.uasset'))

    hull_path = OUT / 'Parts/Expanse/BP_SHP_EXP_Rocinante_01.uasset'
    hull = dump(hull_path, 'hull-before-pdc')
    chosen = None
    for export in hull['Exports']:
        if not isinstance(export.get('Data'), list):
            continue
        for array in export['Data']:
            if array['Name'] != 'AllHardpointData' or not array['Value']:
                continue
            first = array['Value'][0]
            supported = prop(first['Value'], 'TypesSupported')['Value']
            if not any('Ballistic' in item['EnumValue'] for item in supported):
                continue
            grades = prop(first['Value'], 'GradesSupported')['Value']
            if any(item['EnumValue'].endswith('_1') for item in grades):
                chosen = (array, copy.deepcopy(first))
            empty(array)
    if chosen is None:
        raise ValueError('No native primary ballistic collection found')
    array, template = chosen
    for mount in rig['mounts']:
        item = copy.deepcopy(template)
        data = item['Value']
        transform = prop(data, 'Transform')['Value']
        vector(prop(transform, 'Translation'), mount['position'])
        quat = prop(transform, 'Rotation')['Value'][0]['Value']
        for key, value in zip(('X', 'Y', 'Z', 'W'), mount['quaternion']):
            quat[key] = value
        grade = 'EHardpointGrade::HARDPOINTGRADE_' + ('1' if mount['variant'] == 'Negative' else '2')
        supported = prop(data, 'GradesSupported')['Value']
        supported[:] = [copy.deepcopy(supported[0])]
        supported[0]['EnumValue'] = grade
        names(hull, grade)
        fore_mount = mount['source_servo_section'] in (10, 13)
        for field, value in [('bIsYawLimited', fore_mount), ('bIsPitchLimited', True),
                             ('MinYawAngle', -100.0), ('MaxYawAngle', 100.0),
                             ('MinPitchAngle', -5.0), ('MaxPitchAngle', 85.0)]:
            prop(data, field)['Value'] = value
        prop(prop(data, 'Socket')['Value'], 'UsingSocket')['Value'] = False
        array['Value'].append(item)
    write(hull, hull_path)

    system = dump(BASE / 'Systems/Subsystems/BP_SYS_WEAP_PRJ_SR_SD_HRoF_07_Rotary_Cannon.uasset', 'native-cannon')
    source = 'BP_SYS_WEAP_PRJ_SR_SD_HRoF_07_Rotary_Cannon'
    name = 'BP_SYS_EXP_Rocinante_PDC'
    system = replace(system, [('/Game/Blueprints/Systems/Subsystems/' + source,
        '/Game/Blueprints/Systems/Subsystems/Expanse/' + name), (source, name),
        ('/Game/Blueprints/Turrets/' + old, '/Game/Blueprints/Turrets/Expanse/BP_Turret_Rocinante_Negative'),
        (old, 'BP_Turret_Rocinante_Negative')])
    imports = system['Imports']
    package = copy.deepcopy(next(item for item in imports if item['ClassName'] == 'Package'))
    package.update(ObjectName='/Game/Blueprints/Turrets/Expanse/BP_Turret_Rocinante_Positive', OuterIndex=0)
    imports.append(package)
    package_index = -len(imports)
    target = copy.deepcopy(next(item for item in imports if item['ObjectName'] == 'BP_Turret_Rocinante_Negative_C'))
    target.update(ObjectName='BP_Turret_Rocinante_Positive_C', OuterIndex=package_index)
    imports.append(target)
    target_index = -len(imports)
    names(system, package['ObjectName'], target['ObjectName'])
    cdo = next(export for export in system['Exports'] if export['ObjectName'].startswith('Default__'))
    prop(cdo['Data'], 'MaxConcurrentTurrets')['Value'] = 6
    prop(cdo['Data'], 'MinTurretCycleFireStrength')['Value'] = 1.0
    parts = prop(cdo['Data'], 'SystemParts')
    positive = copy.deepcopy(parts['Value'][0])
    prop(positive['Value'], 'PartClass')['Value'] = target_index
    grade = prop(positive['Value'], 'HardpointGrade')
    grade['EnumValue'] = 'EHardpointGrade::HARDPOINTGRADE_2'
    names(system, grade['EnumValue'])
    parts['Value'].append(positive)
    dependencies = cdo['SerializationBeforeSerializationDependencies']
    dependencies.extend(value for value in (package_index, target_index) if value not in dependencies)
    write(system, OUT / ('Systems/Subsystems/Expanse/' + name + '.uasset'))
    print('Created two source PDC variants, six source-aligned hull mounts and native aiming bindings.')


if __name__ == '__main__':
    main()
