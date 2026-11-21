"""Replace inherited Colossus weapons with Mayotte's original gun groups."""
import copy
import json
from pathlib import Path
import build_rocinante_pdc as assets
from build_donnager_weapons import add_class, place

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'obj/expanse-authoring/2687045417'


def actor(source_name, name, source_meshes, gun, swivel, offset, folder='UNN_Mayotte'):
    asset = assets.dump(assets.BASE / ('Turrets/' + source_name + '.uasset'), name + '-source')
    pairs = [('/Game/Blueprints/Turrets/' + source_name, '/Game/Blueprints/Turrets/Expanse/' + name),
             (source_name, name)]
    for before, after in zip(source_meshes, (gun, swivel)):
        pairs.extend([(before, '/Game/Expanse/' + folder + '/' + after), (before.rsplit('/', 1)[1], after)])
    asset = assets.replace(asset, pairs)
    for export in asset['Exports']:
        if export['ObjectName'] == 'GunMesh0':
            assets.vector(assets.prop(export['Data'], 'RelativeLocation'), offset)
        if export['ObjectName'].startswith('Default__'):
            flag = next((p for p in export['Data'] if p['Name'] == 'bDontRotateSwivelMesh'), None)
            if flag:
                flag['Value'] = False
            pitch = next((p for p in export['Data'] if p['Name'] == 'MinHardPitchLimit'), None)
            if pitch:
                pitch['Value'] = -5.0
    assets.write(asset, assets.OUT / ('Turrets/Expanse/' + name + '.uasset'))


def main():
    assets.WORK = FOLDER / 'weapon-assets'
    assets.WORK.mkdir(parents=True, exist_ok=True)
    rig = json.loads((FOLDER / 'weapon-rig.json').read_text())
    rail_source = 'BP_Turret_Titan_InterceptorRailGun_Turret_02'
    rail_meshes = ['/Game/Ships/M02/C28/SM_M02_Railgun_Turret', '/Game/Ships/M02/C28/SM_M02_Railgun_Base']
    for mount in rig['railgun_mounts']:
        side = mount['side']
        actor(rail_source, 'BP_Turret_Mayotte_Railgun_' + side, rail_meshes,
              'Railgun_Mayotte_' + side + '_Gun', 'Railgun_Mayotte_' + side + '_Swivel', mount['gun_relative_location'])
    pdc_source = 'BP_Turret_Titan_03'
    actor(pdc_source, 'BP_Turret_Mayotte_PDC',
          ['/Game/Meshes/Turrets/WM_00/TitanTurret/SM_TitanTurret_001_GUN',
           '/Game/Meshes/Turrets/WM_00/TitanTurret/SM_TitanTurret_001_SWIVEL'],
          'PDC_Mayotte_Gun', 'PDC_Mayotte_Swivel', (0, 0, 0))
    system = assets.dump(assets.OUT / 'Systems/Subsystems/Expanse/BP_SYS_EXP_HeavyRailgun.uasset', 'capital-rail-system')
    system = assets.replace(system, [('BP_SYS_EXP_HeavyRailgun', 'BP_SYS_EXP_Mayotte_Railguns'),
        ('/Game/Blueprints/Turrets/' + rail_source, '/Game/Blueprints/Turrets/Expanse/BP_Turret_Mayotte_Railgun_Dorsal'),
        (rail_source, 'BP_Turret_Mayotte_Railgun_Dorsal')])
    second_class = add_class(system, '/Game/Blueprints/Turrets/Expanse/BP_Turret_Mayotte_Railgun_Ventral',
                             'BP_Turret_Mayotte_Railgun_Ventral')
    cdo = next(e for e in system['Exports'] if e['ObjectName'].startswith('Default__'))
    parts = assets.prop(cdo['Data'], 'SystemParts')['Value']
    second = copy.deepcopy(parts[0])
    assets.prop(second['Value'], 'PartClass')['Value'] = second_class
    assets.prop(second['Value'], 'HardpointGrade')['EnumValue'] = 'EHardpointGrade::HARDPOINTGRADE_2'
    assets.names(system, 'EHardpointGrade::HARDPOINTGRADE_2')
    parts.append(second)
    assets.prop(cdo['Data'], 'MaxConcurrentTurrets')['Value'] = 2
    assets.write(system, assets.OUT / 'Systems/Subsystems/Expanse/BP_SYS_EXP_Mayotte_Railguns.uasset')

    source = 'BP_SYS_WEAP_PRJ_SR_SD_HRoF_07_Rotary_Cannon'
    system = assets.dump(assets.BASE / ('Systems/Subsystems/' + source + '.uasset'), 'native-pdc-system')
    system = assets.replace(system, [('/Game/Blueprints/Systems/Subsystems/' + source,
        '/Game/Blueprints/Systems/Subsystems/Expanse/BP_SYS_EXP_Mayotte_PDC'), (source, 'BP_SYS_EXP_Mayotte_PDC'),
        ('/Game/Blueprints/Turrets/' + pdc_source, '/Game/Blueprints/Turrets/Expanse/BP_Turret_Mayotte_PDC'),
        (pdc_source, 'BP_Turret_Mayotte_PDC'), ('EHardpointGrade::HARDPOINTGRADE_1', 'EHardpointGrade::HARDPOINTGRADE_5')])
    cdo = next(e for e in system['Exports'] if e['ObjectName'].startswith('Default__'))
    assets.prop(cdo['Data'], 'MaxConcurrentTurrets')['Value'] = 42
    assets.prop(cdo['Data'], 'MinTurretCycleFireStrength')['Value'] = 1.0
    # Native cycle/refire scaling distributes fire over eligible mounts. Retain
    # that scaling rather than multiplying damage forty-two times per frame.
    assets.write(system, assets.OUT / 'Systems/Subsystems/Expanse/BP_SYS_EXP_Mayotte_PDC.uasset')

    path = assets.OUT / 'Parts/Expanse/BP_SHP_EXP_Mayotte_01.uasset'
    hull = assets.dump(path, 'hull-before-weapons')
    chosen = None
    for export in hull['Exports']:
        if not isinstance(export.get('Data'), list):
            continue
        for array in export['Data']:
            if array['Name'] != 'AllHardpointData' or not array['Value']:
                continue
            first = array['Value'][0]
            types = assets.prop(first['Value'], 'TypesSupported')['Value']
            if any(item['EnumValue'].endswith('_Ballistic') for item in types):
                chosen = (array, copy.deepcopy(first))
            assets.empty(array)
    if chosen is None:
        raise ValueError('No native ballistic collection')
    for grade, mount in enumerate(rig['railgun_mounts'], 1):
        place(hull, *chosen, mount['position'], grade, 100.0, 75.0)
        data = chosen[0]['Value'][-1]['Value']
        assets.prop(data, 'MinPitchAngle')['Value'] = -5.0
        rotation = assets.prop(assets.prop(data, 'Transform')['Value'], 'Rotation')['Value'][0]['Value']
        rotation.update(zip(('X', 'Y', 'Z', 'W'), mount['quaternion']))
    for mount in rig['pdc_mounts']:
        place(hull, *chosen, mount['position'], 5, 180.0, 90.0)
        data = chosen[0]['Value'][-1]['Value']
        assets.prop(data, 'MinPitchAngle')['Value'] = -5.0
        assets.prop(data, 'MaxPitchAngle')['Value'] = 85.0
        assets.prop(data, 'bIsYawLimited')['Value'] = False
        rotation = assets.prop(assets.prop(data, 'Transform')['Value'], 'Rotation')['Value'][0]['Value']
        rotation.update(zip(('X', 'Y', 'Z', 'W'), mount['quaternion']))
    assets.write(hull, path)
    print('Bound two original Mayotte railguns and 42 source-fitted PDCs, with separate weapon grades.')


if __name__ == '__main__':
    main()
