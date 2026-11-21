"""Generate deterministic additional ship definitions for the Expanse fleet.

The tool only writes to obj/expanse-authoring. It keeps every stock definition
unchanged, gives every imported hull an independent identity and replaces only
the hull-system and ship-data references with the corresponding cloned assets.
"""
import json
from pathlib import Path
import uuid


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'mods/expanse/fleet.json'
SOURCE = ROOT / 'obj/expanse-review/game-SD'
DESTINATION = ROOT / 'obj/expanse-authoring/patch-content/Content/Ships'
NAMESPACE = uuid.UUID('3a44341c-9faf-4a02-8bd0-8b8b8266ad15')


def stable_guid(*values):
    return uuid.uuid5(NAMESPACE, '/'.join(values)).hex.upper()


def blueprint_path(folder, name):
    return f'/Game/Blueprints/{folder}/{name}.{name}'


def build_ship(spec):
    source = json.loads((SOURCE / spec['archetype_ship']).read_text(encoding='utf-8'))
    slug_title = ''.join(piece.title() for piece in spec['slug'].split('_'))
    system_name = f'BP_SYS_EXP_{slug_title}'
    data_name = f'Bp_Sys_ShipData_EXP_{slug_title}'
    system_path = blueprint_path('Systems/Expanse', system_name)
    data_path = blueprint_path('Systems/ShipData', data_name)
    source_system = f"/Game/Blueprints/Systems/{spec['system_source']}.{spec['system_source']}"
    source_data = f"/Game/Blueprints/Systems/ShipData/{spec['data_source']}.{spec['data_source']}"
    source['guidString'] = stable_guid(spec['slug'], 'ship')
    source['fEString'] = spec['display_name']
    source['path'] = '../../../../spacegame/Content/Ships/expanse_' + spec['slug'] + '.json'
    for node in source['nodes']:
        node['guidString'] = stable_guid(spec['slug'], 'node', str(node['nodeId']))
        node['maSystems'] = [system_path if item == source_system else data_path if item == source_data else item
                             for item in node['maSystems']]
        # Premium hull choices inherited from the archetype must never switch
        # an imported vessel back to a stock hull or its stock damage data.
        if 'hull' in node['name'].lower():
            node['maSystems'] = list(next(n['maSystems'] for n in source['nodes'] if n['name'] == 'Hull'))
        # Imported ships have no carrier hangars. Retain native support drones
        # on the utility shuttle, but never inherit a stock fighter complement.
        node['maSystems'] = [item for item in node['maSystems'] if 'LNCHBAY_FIGHTERS' not in item]
        node['maSystems'] = [blueprint_path('Systems/Expanse', 'BP_FX_EXP_' + slug_title)
                             if '/BP_FX_SYS_' in item else item for item in node['maSystems']]
        if spec['slug'] in ('mayotte', 'donnager') and 'Primary' in node['name']:
            weapon = 'BP_SYS_EXP_Donnager_Railguns' if spec['slug'] == 'donnager' else 'BP_SYS_EXP_Mayotte_Railguns'
            node['maSystems'] = [blueprint_path('Systems/Subsystems/Expanse', weapon)]
        if spec['slug'] == 'donnager':
            if 'Secondary' in node['name']:
                node['maSystems'] = [blueprint_path('Systems/Subsystems/Expanse', 'BP_SYS_EXP_Donnager_Torpedoes')]
            # The original source mesh has two rails and six bow tubes. Stock
            # Colossus beam/disarm/drone mounts are unrelated to those parts.
            node['maSystems'] = [item for item in node['maSystems'] if not any(token in item for token in
                ('WEAP_CIWS_', '/BP_SYS_LNCHBAY_', 'BP_SYS_WEAP_MSSLE_04'))]
        if spec['slug'] == 'mayotte':
            if 'Secondary' in node['name']:
                node['maSystems'] = [blueprint_path('Systems/Subsystems/Expanse', 'BP_SYS_EXP_Mayotte_PDC')]
            node['maSystems'] = [item for item in node['maSystems'] if not any(token in item for token in
                ('WEAP_CIWS_', '/BP_SYS_LNCHBAY_', 'BP_SYS_WEAP_MSSLE_04'))]
        if spec['slug'] in ('avalanche', 'chariot'):
            title = spec['slug'].title()
            if 'Primary' in node['name']:
                node['maSystems'] = [blueprint_path('Systems/Subsystems/Expanse', 'BP_SYS_EXP_' + title + '_Cannons')]
            elif 'Secondary' in node['name']:
                node['maSystems'] = [blueprint_path('Systems/Subsystems', 'BP_SYS_ABLTY_BOOST')]
            else:
                # Keep compatible non-directional utility. Stock cannons,
                # healing beams and drone bays have no verified source mount.
                node['maSystems'] = [item for item in node['maSystems'] if not any(token in item for token in
                    ('/BP_SYS_WEAP_', '/BP_SYS_LNCHBAY_', '/BP_SYS_ABLTY_PRJ_', '/BP_SYS_ABLTY_HITSCAN_'))]
        if spec['slug'] in ('razorback', 'epstein_yacht'):
            node['maSystems'] = [item for item in node['maSystems']
                                 if not any(token in item for token in ('/BP_SYS_WEAP_', '/BP_SYS_LNCHBAY_'))]
            if spec['slug'] == 'razorback':
                if 'Primary' in node['name']:
                    node['maSystems'] = [blueprint_path('Systems/Subsystems/Expanse', 'BP_SYS_EXP_Razorback_LightCannon')]
                elif 'Secondary' in node['name']:
                    node['maSystems'] = [blueprint_path('Systems/Subsystems', 'BP_SYS_ABLTY_BOOST')]
        if spec['slug'] == 'rocinante':
            # Original Tachi hull: rotary weapons and missiles, without the
            # later Rocinante railgun, beam emitter or a fictional fighter bay.
            node['maSystems'] = [item for item in node['maSystems'] if not any(token in item for token in
                                 ('Interceptor_Railgun', 'Interceptor_Gauss', 'Radome_', '/BP_SYS_LNCHBAY_'))]
            node['maSystems'] = [item for item in node['maSystems'] if 'WEAP_CIWS_' not in item]
            if 'Primary' in node['name']:
                node['maSystems'] = [blueprint_path('Systems/Subsystems/Expanse', 'BP_SYS_EXP_Rocinante_PDC')]
            elif 'Secondary' in node['name']:
                node['maSystems'] = [blueprint_path('Systems/Subsystems', 'BP_SYS_ABLTY_BOOST')]
            node['maSystems'] = [blueprint_path('Systems/Subsystems/Expanse', 'BP_SYS_EXP_Rocinante_Torpedoes')
                                 if 'BP_SYS_WEAP_MSSLE_19_' in item else item for item in node['maSystems']]
    source['randomizerData']['skins'][0]['gUId'] = stable_guid(spec['slug'], 'default-skin')
    return source


def main():
    specs = json.loads(CONFIG.read_text(encoding='utf-8'))
    DESTINATION.mkdir(parents=True, exist_ok=True)
    generated = []
    for spec in specs:
        ship = build_ship(spec)
        destination = DESTINATION / ('expanse_' + spec['slug'] + '.json')
        destination.write_text(json.dumps(ship, indent=2) + '\n', encoding='utf-8')
        generated.append({'slug': spec['slug'], 'guid': ship['guidString'], 'definition': destination.name,
                          'display_name': spec['display_name'], 'role': spec['role']})
    (DESTINATION / 'expanse-fleet-index.json').write_text(json.dumps(generated, indent=2) + '\n', encoding='utf-8')
    print('Generated', len(generated), 'independent ship definitions.')


if __name__ == '__main__':
    main()
