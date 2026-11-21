"""Build a local candidate Fireline catalog; never modify the shipping responses.

The recorded catalog uses zlib DEFLATE with a non-Adler trailer. Decode its raw
stream, validate its declared size, and emit a standard checked zlib stream.
"""
import base64
import copy
import json
from pathlib import Path
import uuid
import zlib
from build_expanse_fleet import ROOT, SOURCE, CONFIG, build_ship, stable_guid, NAMESPACE


def main():
    responses = json.loads((ROOT / 'server/responses.json').read_text(encoding='utf-8-sig'))
    record = next(x for x in responses if '/ship_tree_table/' in x['request']['url'])
    wrapper = json.loads(record['response']['content'])
    encoded = wrapper['blob']
    packed = base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4))
    raw = zlib.decompress(packed[2:-4], -15)
    if len(raw) != wrapper['decompressedSize']:
        raise ValueError('Recorded catalog size mismatch')
    catalog = json.loads(raw)
    parts = {part['guid']: part for part in catalog['parts']}
    licenses_record = next(x for x in responses if '/licenses?tags' in x['request']['url'])
    licenses = json.loads(licenses_record['response']['content'])
    source_licenses = {item['node']['archetype']: item for item in licenses['licenses']}
    for spec in json.loads(CONFIG.read_text(encoding='utf-8')):
        source = json.loads((SOURCE / spec['archetype_ship']).read_text())
        native = build_ship(spec)
        mapping = {before['guidString']: after['guidString']
                   for before, after in zip(source['nodes'], native['nodes'])}
        original = next(ship for ship in catalog['ships'] if ship['guid'] == source['guidString'])
        ship = copy.deepcopy(original)
        ship.update(guid=native['guidString'], name=spec['display_name'], skins=[],
                    uuid=str(uuid.uuid5(NAMESPACE, spec['slug'] + '/catalog/ship')),
                    description=spec['description'])
        ship['parts'] = [mapping[value] for value in original['parts']]
        new_records = [ship]
        for old_guid, new_guid in mapping.items():
            if old_guid not in parts:
                continue
            part = copy.deepcopy(parts[old_guid])
            part['guid'] = new_guid
            part['uuid'] = str(uuid.uuid5(NAMESPACE, spec['slug'] + '/catalog/' + old_guid))
            part['parts'] = [mapping[value] for value in (part['parts'] or []) if value in mapping]
            if old_guid in original['parts']:
                part['name'] = spec['display_name'] + ' Hull'
                part['description'] = spec['description']
            native_node = next(node for node in native['nodes'] if node['guidString'] == new_guid)
            if not native_node['maSystems']:
                part.update(name='Empty Slot', tooltip='No system fitted', description='No system fitted.', icon='')
            elif any('BP_SYS_EXP_HeavyRailgun' in item for item in native_node['maSystems']):
                part.update(name='Heavy Railgun', tooltip='Charged heavy railgun',
                            description='A charged ballistic railgun using native tracking, recoil and projectile effects.')
            elif any('BP_SYS_EXP_Rocinante_PDC' in item for item in native_node['maSystems']):
                part.update(name='Rocinante PDC Battery', tooltip='Six hull-mounted point-defence cannons',
                            description='The original Rocinante PDC models mounted on native yaw and pitch components.')
            elif any('BP_SYS_EXP_Rocinante_Torpedoes' in item for item in native_node['maSystems']):
                part.update(name='Rocinante Guided Torpedoes', tooltip='Two source-hatch launch sites',
                            description='Native explosive guided torpedoes launched from the dorsal and ventral fore-body bays.')
            elif any('BP_SYS_EXP_Donnager_Railguns' in item for item in native_node['maSystems']):
                part.update(name='Donnager Twin Railguns', tooltip='Two original hull-mounted railguns',
                            description='Two charged ballistic railguns with separate source mounts and muzzle sockets.')
            elif any('BP_SYS_EXP_Donnager_Torpedoes' in item for item in native_node['maSystems']):
                part.update(name='Donnager Bow Torpedoes', tooltip='Six bow launch tubes',
                            description='Guided ordnance launched through the six original forward tubes.')
            elif any('BP_SYS_EXP_Razorback_LightCannon' in item for item in native_node['maSystems']):
                part.update(name='Razorback Light Cannon', tooltip='Single defensive cannon retrofit',
                            description='A single light cannon on an opaque forward hull mount; no torpedo or heavy railgun battery.')
            elif any('BP_SYS_EXP_Mayotte_Railguns' in item for item in native_node['maSystems']):
                part.update(name='Mayotte Twin Railguns', tooltip='Dorsal and ventral railguns',
                            description='Two original heavy railguns on separate articulated mounts.')
            elif any('BP_SYS_EXP_Mayotte_PDC' in item for item in native_node['maSystems']):
                part.update(name='Mayotte PDC Battery', tooltip='42 original surface-mounted cannons',
                            description='The original point-defence cannons, fired through native ballistic cycle and surface arcs.')
            elif any('BP_SYS_EXP_Avalanche_Cannons' in item or 'BP_SYS_EXP_Chariot_Cannons' in item for item in native_node['maSystems']):
                part.update(name=spec['display_name'] + ' Cannon Battery', tooltip='Two original articulated cannons',
                            description='Two source-mounted ballistic cannons with their own bore sockets and outward firing arcs.')
            elif spec['slug'] in ('rocinante', 'razorback', 'avalanche', 'chariot') and any('BP_SYS_ABLTY_BOOST' in item for item in native_node['maSystems']):
                part.update(name='Propulsion Boost', tooltip='Temporary propulsion boost',
                            description='A native short-duration propulsion boost for the racing pinnace.')
            elif native_node['maSystems'] and all('BP_SYS_ENGINE_' in item for item in native_node['maSystems']):
                part.update(name='Jump Drive', tooltip='Jump and return drive',
                            description='Native jump and return functions.')
            catalog['parts'].append(part)
            new_records.append(part)
        catalog['ships'].append(ship)
        # The frontend discovers roster entries through manufacturer ship lists,
        # not only through the flat ships collection. Keep the compatible stock
        # manufacturer/icon group used by this ship's gameplay archetype.
        manufacturer = next(group for group in catalog['manus'] if original['guid'] in group['ships'])
        manufacturer['ships'].append(ship['guid'])
        for entry in new_records:
            old_uuid = original['uuid'] if entry is ship else parts[next(
                key for key, value in mapping.items() if value == entry['guid'])]['uuid']
            # Some stock alternatives were unowned in the recording. The
            # Fireline ownership envelope is shared; imported parts are granted
            # explicitly using their new, catalog-backed archetype identity.
            template = source_licenses.get(old_uuid, source_licenses[original['uuid']])
            license = copy.deepcopy(template)
            license['_id'] = str(uuid.uuid5(NAMESPACE, spec['slug'] + '/license/' + old_uuid))
            license['node']['archetype'] = entry['uuid']
            license['node']['item'] = str(uuid.uuid5(NAMESPACE, spec['slug'] + '/item/' + old_uuid))
            licenses['licenses'].append(license)
    raw = json.dumps(catalog, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    wrapper['decompressedSize'] = len(raw)
    wrapper['blob'] = base64.urlsafe_b64encode(zlib.compress(raw)).decode('ascii').rstrip('=')
    record['response']['content'] = json.dumps(wrapper)
    licenses_record['response']['content'] = json.dumps(licenses)
    destination = ROOT / 'obj/expanse-authoring/candidate-responses.json'
    destination.write_text(json.dumps(responses, indent=2), encoding='utf-8')
    print('Candidate catalog:', len(catalog['ships']), 'ships; local candidate only.')


if __name__ == '__main__':
    main()
