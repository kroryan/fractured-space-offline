"""Cross-check candidate account data against the generated native definitions."""
import base64
import json
from pathlib import Path
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / 'obj/expanse-authoring/candidate-responses.json'


@unittest.skipUnless(CANDIDATE.exists(), 'Build the local candidate catalog first.')
class FleetCatalogTests(unittest.TestCase):
    def test_civilian_and_original_tachi_weapon_constraints(self):
        folder = ROOT / 'obj/expanse-authoring/patch-content/Content/Ships'
        for slug in ('razorback', 'epstein_yacht', 'rocinante'):
            ship = json.loads((folder / ('expanse_' + slug + '.json')).read_text())
            systems = [item for node in ship['nodes'] for item in node['maSystems']]
            if slug == 'epstein_yacht':
                self.assertFalse(any('/BP_SYS_WEAP_' in item or '/BP_SYS_LNCHBAY_' in item for item in systems))
            elif slug == 'razorback':
                self.assertTrue(any('BP_SYS_EXP_Razorback_LightCannon' in item for item in systems))
                self.assertTrue(any('BP_SYS_ABLTY_BOOST' in item for item in systems))
                self.assertFalse(any('/BP_SYS_WEAP_' in item or 'WEAP_CIWS' in item for item in systems))
            else:
                self.assertTrue(any('BP_SYS_EXP_Rocinante_PDC' in item for item in systems))
                self.assertTrue(any('BP_SYS_EXP_Rocinante_Torpedoes' in item for item in systems))
                self.assertFalse(any('Railgun' in item or 'Gauss' in item or 'Radome_' in item for item in systems))
            root = next(node for node in ship['nodes'] if node['name'] == 'Hull')
            for node in ship['nodes']:
                if 'hull' in node['name'].lower():
                    self.assertEqual(node['maSystems'], root['maSystems'])

    def test_capital_primary_railguns_and_no_fighter_bays(self):
        folder = ROOT / 'obj/expanse-authoring/patch-content/Content/Ships'
        for path in folder.glob('expanse_*.json'):
            ship = json.loads(path.read_text())
            for node in ship['nodes']:
                self.assertFalse(any('LNCHBAY_FIGHTERS' in item for item in node['maSystems']))
                if ship['fEString'] in ('UNN Mayotte', 'MCRN Donnager') and 'Primary' in node['name']:
                    self.assertEqual(len(node['maSystems']), 1)
                    expected = 'BP_SYS_EXP_Donnager_Railguns' if ship['fEString'] == 'MCRN Donnager' else 'BP_SYS_EXP_Mayotte_Railguns'
                    self.assertIn(expected, node['maSystems'][0])

    def test_additional_fleet_references_and_ownership(self):
        responses = json.loads(CANDIDATE.read_text())
        record = next(x for x in responses if '/ship_tree_table/' in x['request']['url'])
        wrapper = json.loads(record['response']['content'])
        encoded = wrapper['blob']
        raw = zlib.decompress(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)))
        self.assertEqual(len(raw), wrapper['decompressedSize'])
        catalog = json.loads(raw)
        parts = {part['guid']: part for part in catalog['parts']}
        self.assertEqual(len(parts), len(catalog['parts']))
        licenses = json.loads(next(x for x in responses if '/licenses?tags' in x['request']['url'])['response']['content'])
        owned = {item['node']['archetype'] for item in licenses['licenses']}
        for spec in json.loads((ROOT / 'mods/expanse/fleet.json').read_text()):
            native = json.loads((ROOT / ('obj/expanse-authoring/patch-content/Content/Ships/expanse_' + spec['slug'] + '.json')).read_text())
            ship = next(s for s in catalog['ships'] if s['guid'] == native['guidString'])
            self.assertEqual(ship['name'], spec['display_name'])
            self.assertEqual(sum(ship['guid'] in group['ships'] for group in catalog['manus']), 1)
            self.assertIn(ship['uuid'], owned)
            native_guids = {node['guidString'] for node in native['nodes']}
            pending, visited = list(ship['parts']), set()
            while pending:
                guid = pending.pop()
                if guid in visited:
                    continue
                visited.add(guid)
                self.assertIn(guid, native_guids)
                self.assertIn(guid, parts)
                self.assertIn(parts[guid]['uuid'], owned)
                pending.extend(parts[guid]['parts'] or [])
            self.assertTrue(visited)


if __name__ == '__main__':
    unittest.main()
