"""Compare frame conversion against an actual asymmetric Unreal import."""
import json
from pathlib import Path
import sys
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from expanse_axes import blender_to_native, source_to_native, source_to_blender


class FrameTests(unittest.TestCase):
    def test_shared_source_to_editor_to_native_frame(self):
        points = np.array([[1, 2, 3], [-4, 5, -6]])
        for ident in ['2211361535', '2224316655', '2368610280', '2375119898', '2375181309', '2687045417', '2687094193']:
            np.testing.assert_allclose(blender_to_native(source_to_blender(points, ident)), source_to_native(points, ident))

    def test_against_imported_asymmetric_fixture(self):
        path = ROOT / 'obj/expanse-authoring/axis-calibration/asset.json'
        if not path.exists():
            self.skipTest('Run and dump the actual Unreal axis calibration first.')
        asset = json.loads(path.read_text())
        data = next(export['Data'] for export in asset['Exports'] if export['ObjectName'] == 'AxisCalibration')
        bounds = next(item for item in data if item['Name'] == 'ExtendedBounds')['Value']
        def read(name):
            value = next(item for item in bounds if item['Name'] == name)['Value'][0]['Value']
            return np.array([float(value[axis]) for axis in 'XYZ'])
        actual_min, actual_max = read('Origin') - read('BoxExtent'), read('Origin') + read('BoxExtent')
        imported = blender_to_native([[0, 0, 0], [1, 0, 0], [0, 2, 0], [0, 0, 3]])
        np.testing.assert_allclose(actual_min, imported.min(0), atol=1e-5)
        np.testing.assert_allclose(actual_max, imported.max(0), atol=1e-5)


if __name__ == '__main__':
    unittest.main()
