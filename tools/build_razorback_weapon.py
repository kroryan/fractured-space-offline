"""Bind the requested single light-cannon retrofit and remove stock gun mounts."""
import copy
import json
from pathlib import Path
import build_rocinante_pdc as assets
from build_donnager_weapons import place

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'obj/expanse-authoring/2224316655'


def main():
    assets.WORK = FOLDER / 'weapon-assets'
    assets.WORK.mkdir(parents=True, exist_ok=True)
    rig = json.loads((FOLDER / 'cannon-rig.json').read_text())
    source = 'BP_Turret_Titan_03'
    name = 'BP_Turret_Razorback_LightCannon'
    turret = assets.dump(assets.BASE / ('Turrets/' + source + '.uasset'), 'native-light-turret')
    turret = assets.replace(turret, [
        ('/Game/Blueprints/Turrets/' + source, '/Game/Blueprints/Turrets/Expanse/' + name), (source, name),
        ('/Game/Meshes/Turrets/WM_00/TitanTurret/SM_TitanTurret_001_GUN', '/Game/Expanse/Razorback/Cannon_Razorback_Gun'),
        ('SM_TitanTurret_001_GUN', 'Cannon_Razorback_Gun'),
        ('/Game/Meshes/Turrets/WM_00/TitanTurret/SM_TitanTurret_001_SWIVEL', '/Game/Expanse/Razorback/Cannon_Razorback_Swivel'),
        ('SM_TitanTurret_001_SWIVEL', 'Cannon_Razorback_Swivel')])
    imports = turret['Imports']
    package = copy.deepcopy(next(item for item in imports if item['ClassName'] == 'Package'))
    package.update(ObjectName='/Game/Expanse/Razorback/Cannon_Razorback_Base', OuterIndex=0)
    imports.append(package)
    package_index = -len(imports)
    mesh = copy.deepcopy(next(item for item in imports if item['ClassName'] == 'StaticMesh'))
    mesh.update(ObjectName='Cannon_Razorback_Base', OuterIndex=package_index)
    imports.append(mesh)
    mesh_index = -len(imports)
    assets.names(turret, package['ObjectName'], mesh['ObjectName'])
    gun = next(export for export in turret['Exports'] if export['ObjectName'] == 'GunMesh0')
    assets.vector(assets.prop(gun['Data'], 'RelativeLocation'), (0, 0, 0))
    base = next(export for export in turret['Exports'] if export['ObjectName'] == 'BaseMesh0')
    prop = copy.deepcopy(assets.prop(gun['Data'], 'StaticMesh'))
    prop['Value'] = mesh_index
    base['Data'].append(prop)
    base['SerializationBeforeSerializationDependencies'].extend([package_index, mesh_index])
    cdo = next(export for export in turret['Exports'] if export['ObjectName'].startswith('Default__'))
    assets.prop(cdo['Data'], 'bDontRotateSwivelMesh')['Value'] = False
    assets.prop(cdo['Data'], 'MinHardPitchLimit')['Value'] = -5.0
    assets.write(turret, assets.OUT / ('Turrets/Expanse/' + name + '.uasset'))

    source_system = 'BP_SYS_WEAP_PRJ_SR_SD_HRoF_07_Rotary_Cannon'
    system_name = 'BP_SYS_EXP_Razorback_LightCannon'
    system = assets.dump(assets.BASE / ('Systems/Subsystems/' + source_system + '.uasset'), 'native-cannon')
    system = assets.replace(system, [('/Game/Blueprints/Systems/Subsystems/' + source_system,
        '/Game/Blueprints/Systems/Subsystems/Expanse/' + system_name), (source_system, system_name),
        ('/Game/Blueprints/Turrets/' + source, '/Game/Blueprints/Turrets/Expanse/' + name), (source, name)])
    cdo = next(export for export in system['Exports'] if export['ObjectName'].startswith('Default__'))
    for field, value in [('MaxConcurrentTurrets', 1), ('MinTurretCycleFireStrength', 1.0),
                         ('OptimumTurretCycleFireStrength', 1.0), ('bUseTurretCycleFire', False),
                         ('bModifyRefireForTurretCycle', False), ('RefireRate', 0.15)]:
        assets.prop(cdo['Data'], field)['Value'] = value
    assets.write(system, assets.OUT / ('Systems/Subsystems/Expanse/' + system_name + '.uasset'))

    path = assets.OUT / 'Parts/Expanse/BP_SHP_EXP_Razorback_01.uasset'
    hull = assets.dump(path, 'hull-before-cannon')
    chosen = None
    for export in hull['Exports']:
        if not isinstance(export.get('Data'), list):
            continue
        for array in export['Data']:
            if array['Name'] != 'AllHardpointData' or not array['Value']:
                continue
            first = array['Value'][0]
            supported = assets.prop(first['Value'], 'TypesSupported')['Value']
            if any(item['EnumValue'].endswith('_Ballistic') for item in supported):
                chosen = (array, copy.deepcopy(first))
            assets.empty(array)
    if chosen is None:
        raise ValueError('Missing native ballistic hardpoint collection')
    place(hull, *chosen, rig['position'], 1, 85.0, 65.0)
    transform = assets.prop(chosen[0]['Value'][0]['Value'], 'Transform')['Value']
    rotation = assets.prop(transform, 'Rotation')['Value'][0]['Value']
    rotation.update(zip(('X', 'Y', 'Z', 'W'), rig['quaternion']))
    # The dorsal retrofit must never pitch below its mounting surface.
    assets.prop(chosen[0]['Value'][0]['Value'], 'MinPitchAngle')['Value'] = -5.0
    assets.write(hull, path)
    print('Bound one surface-mounted Razorback light cannon; removed inherited gun/torpedo placements.')


if __name__ == '__main__':
    main()
