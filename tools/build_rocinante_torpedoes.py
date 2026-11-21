"""Bind two source-hatch launch sites using native static guided-torpedo parts."""
import copy
import json
from pathlib import Path
import build_rocinante_pdc as assets
from build_donnager_weapons import add_class, place

ROOT = Path(__file__).resolve().parents[1]


def torpedo_system(name, concurrent, grade):
    source = 'BP_SYS_WEAP_MSSLE_04'
    system = assets.dump(assets.BASE / ('Systems/Subsystems/' + source + '.uasset'), name + '-source')
    system = assets.replace(system, [('/Game/Blueprints/Systems/Subsystems/' + source,
        '/Game/Blueprints/Systems/Subsystems/Expanse/' + name), (source, name)])
    part_class = add_class(system, '/Game/Blueprints/Turrets/StaticTurret_SmallSingle_Invis', 'StaticTurret_SmallSingle_Invis')
    cdo = next(e for e in system['Exports'] if e['ObjectName'].startswith('Default__'))
    part = assets.prop(cdo['Data'], 'SystemParts')['Value'][0]
    assets.prop(part['Value'], 'PartClass')['Value'] = part_class
    assets.prop(part['Value'], 'HardpointGrade')['EnumValue'] = 'EHardpointGrade::HARDPOINTGRADE_' + str(grade)
    assets.names(system, 'EHardpointGrade::HARDPOINTGRADE_' + str(grade), 'MaxConcurrentTurrets', 'IntProperty')
    field = next((p for p in cdo['Data'] if p['Name'] == 'MaxConcurrentTurrets'), None)
    if field is None:
        field = {'$type': 'UAssetAPI.PropertyTypes.Objects.IntPropertyData, UAssetAPI', 'Name': 'MaxConcurrentTurrets',
                 'ArrayIndex': 0, 'PropertyGuid': None, 'IsZero': False, 'PropertyTagFlags': 'None',
                 'PropertyTypeName': None, 'PropertyTagExtensions': 'NoExtension', 'Value': concurrent}
        cdo['Data'].append(field)
    else:
        field['Value'] = concurrent
    assets.write(system, assets.OUT / ('Systems/Subsystems/Expanse/' + name + '.uasset'))


def main():
    folder = ROOT / 'obj/expanse-authoring/2211361535'
    assets.WORK = folder / 'torpedo-assets'
    assets.WORK.mkdir(parents=True, exist_ok=True)
    rig = json.loads((folder / 'torpedo-rig.json').read_text())
    torpedo_system('BP_SYS_EXP_Rocinante_Torpedoes', 2, 5)
    # The capital ship uses the same native explosive projectile family, with
    # six separately mapped physical bow tubes instead of interceptor EMPs.
    torpedo_system('BP_SYS_EXP_Donnager_Torpedoes', 6, 1)
    path = assets.OUT / 'Parts/Expanse/BP_SHP_EXP_Rocinante_01.uasset'
    hull = assets.dump(path, 'hull-before-torpedoes')
    chosen = None
    for export in hull['Exports']:
        if not isinstance(export.get('Data'), list):
            continue
        for array in export['Data']:
            if array['Name'] != 'AllHardpointData' or not array['Value']:
                continue
            first = array['Value'][0]
            kinds = assets.prop(first['Value'], 'TypesSupported')['Value']
            if any(p['EnumValue'].endswith('_Ballistic') for p in kinds):
                continue
            if any(p['EnumValue'].endswith('_Missile') for p in kinds):
                chosen = (array, copy.deepcopy(first))
            assets.empty(array)
    if chosen is None:
        raise ValueError('No native missile hardpoint collection')
    for port in rig['ports']:
        place(hull, *chosen, port['position'], 5, 180.0, 90.0)
        data = chosen[0]['Value'][-1]['Value']
        # The native StaticTurret retains its fixed launch direction while the
        # guided subsystem can acquire targets outside that initial direction.
        assets.prop(data, 'bIsYawLimited')['Value'] = False
        assets.prop(data, 'bIsPitchLimited')['Value'] = False
        rotation = assets.prop(assets.prop(data, 'Transform')['Value'], 'Rotation')['Value'][0]['Value']
        rotation.update(zip(('X', 'Y', 'Z', 'W'), port['quaternion']))
    assets.write(hull, path)
    path = assets.OUT / 'Parts/Expanse/BP_SHP_EXP_EpsteinYacht_01.uasset'
    yacht = assets.dump(path, 'unarmed-yacht-hull')
    for export in yacht['Exports']:
        if not isinstance(export.get('Data'), list):
            continue
        for array in export['Data']:
            if array['Name'] == 'AllHardpointData':
                assets.empty(array)
    assets.write(yacht, path)
    print('Bound two source-hatch launch sites, retained static launch directions and cleared unarmed yacht mounts.')


if __name__ == '__main__':
    main()
