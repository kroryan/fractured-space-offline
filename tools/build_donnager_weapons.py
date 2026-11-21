"""Bind Donnager's two original railguns and six original bow launch tubes.

This authoring step removes all inherited Colossus weapon placements. It does
not infer a PDC count from hull greebles or approve in-game firing behavior.
"""
import copy
import json
from pathlib import Path
import numpy as np
import build_rocinante_pdc as assets
from expanse_axes import source_to_native

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'obj/expanse-authoring/2375119898'
OUT = assets.OUT


def add_class(asset, package_name, class_name):
    imports = asset['Imports']
    package = copy.deepcopy(next(item for item in imports if item['ClassName'] == 'Package'))
    package.update(ObjectName=package_name, OuterIndex=0)
    imports.append(package)
    package_index = -len(imports)
    target = copy.deepcopy(next(item for item in imports if item['ClassName'] == 'BlueprintGeneratedClass'))
    target.update(ObjectName=class_name + '_C', OuterIndex=package_index)
    imports.append(target)
    target_index = -len(imports)
    assets.names(asset, package_name, class_name + '_C')
    cdo = next(export for export in asset['Exports'] if export['ObjectName'].startswith('Default__'))
    dependencies = cdo['SerializationBeforeSerializationDependencies']
    dependencies.extend(value for value in (package_index, target_index) if value not in dependencies)
    return target_index


def place(asset, array, template, position, grade, yaw, pitch):
    item = copy.deepcopy(template)
    data = item['Value']
    transform = assets.prop(data, 'Transform')['Value']
    assets.vector(assets.prop(transform, 'Translation'), position)
    rotation = assets.prop(transform, 'Rotation')['Value'][0]['Value']
    rotation.update(X=0.0, Y=0.0, Z=0.0, W=1.0)
    assets.vector(assets.prop(transform, 'Scale3D'), (1, 1, 1))
    supported = assets.prop(data, 'GradesSupported')['Value']
    supported[:] = [copy.deepcopy(supported[0])]
    supported[0]['EnumValue'] = 'EHardpointGrade::HARDPOINTGRADE_' + str(grade)
    assets.names(asset, supported[0]['EnumValue'])
    for field, value in [('bIsYawLimited', True), ('bIsPitchLimited', True),
                         ('MinYawAngle', -yaw), ('MaxYawAngle', yaw),
                         ('MinPitchAngle', -pitch), ('MaxPitchAngle', pitch)]:
        assets.prop(data, field)['Value'] = value
    # These source mounts use explicit hull-relative transforms, not a socket
    # inherited from a different ship's static mesh.
    assets.prop(assets.prop(data, 'Socket')['Value'], 'UsingSocket')['Value'] = False
    array['Value'].append(item)


def main():
    assets.WORK = FOLDER / 'weapon-assets'
    assets.WORK.mkdir(parents=True, exist_ok=True)
    rig = json.loads((FOLDER / 'railgun-rig.json').read_text())
    native_name = 'BP_Turret_Titan_InterceptorRailGun_Turret_02'
    turret = assets.dump(assets.BASE / ('Turrets/' + native_name + '.uasset'), 'native-rail-turret')
    for side in ('Port', 'Starboard'):
        name = 'BP_Turret_Donnager_Railgun_' + side
        actor = assets.replace(turret, [
            ('/Game/Blueprints/Turrets/' + native_name, '/Game/Blueprints/Turrets/Expanse/' + name),
            (native_name, name),
            ('/Game/Ships/M02/C28/SM_M02_Railgun_Base', '/Game/Expanse/MCRN_Donnager/Railgun_Donnager_' + side + '_Swivel'),
            ('SM_M02_Railgun_Base', 'Railgun_Donnager_' + side + '_Swivel'),
            ('/Game/Ships/M02/C28/SM_M02_Railgun_Turret', '/Game/Expanse/MCRN_Donnager/Railgun_Donnager_' + side + '_Gun'),
            ('SM_M02_Railgun_Turret', 'Railgun_Donnager_' + side + '_Gun')])
        gun = next(export for export in actor['Exports'] if export['ObjectName'] == 'GunMesh0')
        assets.vector(assets.prop(gun['Data'], 'RelativeLocation'), (0, 0, 0))
        assets.write(actor, OUT / ('Turrets/Expanse/' + name + '.uasset'))

    system = assets.dump(OUT / 'Systems/Subsystems/Expanse/BP_SYS_EXP_HeavyRailgun.uasset', 'capital-rail-system')
    system = assets.replace(system, [('BP_SYS_EXP_HeavyRailgun', 'BP_SYS_EXP_Donnager_Railguns'),
        ('/Game/Blueprints/Turrets/' + native_name, '/Game/Blueprints/Turrets/Expanse/BP_Turret_Donnager_Railgun_Port'),
        (native_name, 'BP_Turret_Donnager_Railgun_Port')])
    second_class = add_class(system, '/Game/Blueprints/Turrets/Expanse/BP_Turret_Donnager_Railgun_Starboard',
                             'BP_Turret_Donnager_Railgun_Starboard')
    cdo = next(export for export in system['Exports'] if export['ObjectName'].startswith('Default__'))
    parts = assets.prop(cdo['Data'], 'SystemParts')['Value']
    second = copy.deepcopy(parts[0])
    assets.prop(second['Value'], 'PartClass')['Value'] = second_class
    assets.prop(second['Value'], 'HardpointGrade')['EnumValue'] = 'EHardpointGrade::HARDPOINTGRADE_2'
    assets.names(system, 'EHardpointGrade::HARDPOINTGRADE_2')
    parts.append(second)
    assets.prop(cdo['Data'], 'MaxConcurrentTurrets')['Value'] = 2
    assets.write(system, OUT / 'Systems/Subsystems/Expanse/BP_SYS_EXP_Donnager_Railguns.uasset')

    source = 'BP_SYS_WEAP_MSSLE_19_Interceptor'
    torpedoes = assets.dump(assets.BASE / ('Systems/Subsystems/' + source + '.uasset'), 'native-torpedoes')
    torpedoes = assets.replace(torpedoes, [('/Game/Blueprints/Systems/Subsystems/' + source,
        '/Game/Blueprints/Systems/Subsystems/Expanse/BP_SYS_EXP_Donnager_Torpedoes'),
        (source, 'BP_SYS_EXP_Donnager_Torpedoes'),
        ('EHardpointGrade::HARDPOINTGRADE_5', 'EHardpointGrade::HARDPOINTGRADE_1')])
    assets.write(torpedoes, OUT / 'Systems/Subsystems/Expanse/BP_SYS_EXP_Donnager_Torpedoes.uasset')

    hull_path = OUT / 'Parts/Expanse/BP_SHP_EXP_Donnager_01.uasset'
    hull = assets.dump(hull_path, 'hull-before-weapons')
    collections = {}
    for export in hull['Exports']:
        if not isinstance(export.get('Data'), list):
            continue
        for array in export['Data']:
            if array['Name'] != 'AllHardpointData' or not array['Value']:
                continue
            first = array['Value'][0]
            types = assets.prop(first['Value'], 'TypesSupported')['Value']
            for kind in ('Ballistic', 'Missile'):
                if any(item['EnumValue'].endswith('_' + kind) for item in types):
                    collections.setdefault(kind, (array, copy.deepcopy(first)))
            assets.empty(array)
    for grade, mount in enumerate(rig['mounts'], 1):
        place(hull, *collections['Ballistic'], mount['position'], grade, 8.0, 5.0)
    review = json.loads((FOLDER / 'component-review.json').read_text())
    ports = [item for item in review if item['section'] == 0 and item['component'] in (6128, 6129, 7349, 7350, 8135, 8136)]
    if len(ports) != 6 or any(item['triangles'] != 252 for item in ports):
        raise ValueError('Original bow launch-tube geometry changed')
    for port in ports:
        center = np.array(port['center'])
        center[2] = port['upper'][2]
        position = source_to_native(center, '2375119898') * rig['scale']
        place(hull, *collections['Missile'], position.tolist(), 1, 0.0, 0.0)
    assets.write(hull, hull_path)
    (FOLDER / 'weapon-binding-review.json').write_text(json.dumps({
        'railgun_count': 2, 'railgun_grades': [1, 2], 'max_concurrent_railguns': 2,
        'bow_launch_tube_count': 6, 'source_launch_tube_components': [p['component'] for p in ports],
        'inherited_weapon_mounts_removed': True, 'requires_gameplay_validation': True}, indent=2) + '\n')
    print('Bound two source railguns and six source bow launch tubes; gameplay validation remains required.')


if __name__ == '__main__':
    main()
