"""Check the rendered files expected by native ship-selection views."""
import json
from pathlib import Path
import sys
import unittest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_expanse_fleet import stable_guid


class FleetPortraitTests(unittest.TestCase):
    def test_all_native_portrait_paths_are_present_and_framed(self):
        sizes = {'main': (464, 207), 'store': (464, 207), 'large': (1631, 652),
                 'bronze': (278, 124), 'silver': (278, 124), 'gold': (278, 124)}
        for spec in json.loads((ROOT / 'mods/expanse/fleet.json').read_text()):
            directory = ROOT / 'obj/expanse-authoring/portraits' / stable_guid(spec['slug'], 'ship')
            for name, size in sizes.items():
                with self.subTest(ship=spec['slug'], view=name):
                    image = Image.open(directory / (name + '.png'))
                    self.assertEqual(image.size, size)
                    self.assertEqual(image.mode, 'RGBA')
                    bounds = image.getchannel('A').getbbox()
                    self.assertIsNotNone(bounds)
                    self.assertGreater(bounds[0], 0)
                    self.assertGreater(bounds[1], 0)
                    self.assertLess(bounds[2], size[0])
                    self.assertLess(bounds[3], size[1])
                    # A selector thumbnail must show a readable ship instead
                    # of a tiny object surrounded by unused transparent space.
                    occupancy = max((bounds[2] - bounds[0]) / size[0], (bounds[3] - bounds[1]) / size[1])
                    self.assertGreater(occupancy, 0.85)


if __name__ == '__main__':
    unittest.main()
