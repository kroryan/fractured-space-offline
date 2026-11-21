"""Bind the original two-cannon groups on Avalanche and Chariot."""
import copy
import json
from pathlib import Path
import build_rocinante_pdc as assets
from build_donnager_weapons import add_class, place
from build_mayotte_weapons import actor

ROOT = Path(__file__).resolve().parents[1]


def build(ident, title, folder, rate):
    directory = ROOT / 'obj/expanse-authoring' / ident
    assets.WORK = directory / 'weapon-assets'
    assets.WORK.mkdir(parents=True, exist_ok=True)
    rig = json.loads((directory / 'weapon-rig.json').read_text())
    source_actor = 'BP_Turret_Titan_03'
    meshes = ['/Game/Meshes/Turrets/WM_00/TitanTurret/SM_TitanTurret_001_GUN',
              '/Game/Meshes/Turrets/WM_00/TitanTurret/SM_TitanTurret_001_SWIVEL']
    for mount in rig['cannon_mounts']:
        side = mount['side']
        actor(source_actor, 'BP_Turret_' + title + '_Cannon_' + side, meshes,
              'Cannon_' + title + '_' + side + '_Gun', 'Cannon_' + title + '_' + side + '_Swivel',
              mount['gun_relative_location'], folder)
    source = 'BP_SYS_WEAP_PRJ_SR_SD_HRoF_07_Rotary_Cannon'
    name = 'BP_SYS_EXP_' + title + '_Cannons'
    first, second = [mount['side'] for mount in rig['cannon_mounts']]
    system = assets.dump(assets.BASE / ('Systems/Subsystems/' + source + '.uasset'), 'native-cannon-system')
    system = assets.replace(system, [('/Game/Blueprints/Systems/Subsystems/' + source,
        '/Game/Blueprints/Systems/Subsystems/Expanse/' + name), (source, name),
        ('/Game/Blueprints/Turrets/' + source_actor,
         '/Game/Blueprints/Turrets/Expanse/BP_Turret_' + title + '_Cannon_' + first),
        (source_actor, 'BP_Turret_' + title + '_Cannon_' + first)])
    second_name = 'BP_Turret_' + title + '_Cannon_' + second
    second_class = add_class(system, '/Game/Blueprints/Turrets/Expanse/' + second_name, second_name)
    cdo = next(e for e in system['Exports'] if e['ObjectName'].startswith('Default__'))
    parts = assets.prop(cdo['Data'], 'SystemParts')['Value']
    part = copy.deepcopy(parts[0])
    assets.prop(part['Value'], 'PartClass')['Value'] = second_class
    assets.prop(part['Value'], 'HardpointGrade')['EnumValue'] = 'EHardpointGrade::HARDPOINTGRADE_2'
    assets.names(system, 'EHardpointGrade::HARDPOINTGRADE_2')
    parts.append(part)
    for field, value in [('MaxConcurrentTurrets', 2), ('MinTurretCycleFireStrength', 1.0),
                         ('OptimumTurretCycleFireStrength', 2.0), ('RefireRate', rate)]:
        assets.prop(cdo['Data'], field)['Value'] = value
    assets.write(system, assets.OUT / ('Systems/Subsystems/Expanse/' + name + '.uasset'))
    path = assets.OUT / ('Parts/Expanse/BP_SHP_EXP_' + title + '_01.uasset')
    hull = assets.dump(path, 'hull-before-weapons')
    chosen = None
    for export in hull['Exports']:
        if not isinstance(export.get('Data'), list):
            continue
        for array in export['Data']:
            if array['Name'] != 'AllHardpointData' or not array['Value']:
                continue
            first = array['Value'][0]
            if any(item['EnumValue'].endswith('_Ballistic') for item in assets.prop(first['Value'], 'TypesSupported')['Value']):
                chosen = (array, copy.deepcopy(first))
            assets.empty(array)
    if chosen is None:
        raise ValueError('No compatible native ballistic collection')
    for grade, mount in enumerate(rig['cannon_mounts'], 1):
        place(hull, *chosen, mount['position'], grade, 180.0, 85.0)
        data = chosen[0]['Value'][-1]['Value']
        assets.prop(data, 'MinPitchAngle')['Value'] = -5.0
        assets.prop(data, 'bIsYawLimited')['Value'] = title == 'Chariot'
        if title == 'Chariot':
            assets.prop(data, 'MinYawAngle')['Value'] = -100.0
            assets.prop(data, 'MaxYawAngle')['Value'] = 100.0
        rotation = assets.prop(assets.prop(data, 'Transform')['Value'], 'Rotation')['Value'][0]['Value']
        rotation.update(zip(('X', 'Y', 'Z', 'W'), mount['quaternion']))
    assets.write(hull, path)
    print(title + ': bound two original cannons and removed inherited stock weapon placements.')


def main():
    build('2687094193', 'Avalanche', 'MCRN_Avalanche', 0.1)
    build('2375181309', 'Chariot', 'MCRN_Chariot_Type_Dropship', 0.2)


if __name__ == '__main__':
    main()
