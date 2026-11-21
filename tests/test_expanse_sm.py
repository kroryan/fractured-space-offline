import struct
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
try:
    import numpy as np
    from expanse_sm import read_sm
except ImportError:
    np = None


@unittest.skipIf(np is None, 'NumPy is an optional asset-authoring dependency')
class SM02Tests(unittest.TestCase):
    def model(self, packed):
        header = struct.pack('<4sI4fI', b'SM02', 1, 0, 0, 0, 10, 4 if packed else 0)
        mesh = struct.pack('<IIHH7f', 3, 3, 0, 0, 10, 20, 30, 2, .5, .5, .5)
        vertices = b''
        for x, y in [(0, 0), (1, 0), (0, 1)]:
            if packed:
                vertices += struct.pack('<4hII2h', x * 32767, y * 32767, 0, 123,
                                        511 << 20, 511, x * 32767, y * 32767)
            else:
                vertices += struct.pack('<12f', x, y, 0, 0, 0, 1, 1, 0, 0, 1, x, y)
        return header + mesh + vertices + struct.pack('<3I', 0, 1, 2)

    def test_packed_positions_uv_normals_and_indices(self):
        mesh = read_sm(self.model(True))[0]
        np.testing.assert_allclose(mesh.positions, [[10, 20, 30], [12, 20, 30], [10, 22, 30]])
        np.testing.assert_allclose(mesh.uv, [[.5, .5], [1, .5], [.5, 1]])
        np.testing.assert_allclose(mesh.normals, [[0, 0, 1]] * 3)
        np.testing.assert_array_equal(mesh.triangles, [[0, 1, 2]])

    def test_uncompressed_vertices_remain_unchanged(self):
        mesh = read_sm(self.model(False))[0]
        np.testing.assert_allclose(mesh.positions, [[0, 0, 0], [1, 0, 0], [0, 1, 0]])
        np.testing.assert_allclose(mesh.uv, [[0, 0], [1, 0], [0, 1]])

    def test_reject_truncation_and_invalid_indices(self):
        with self.assertRaises(ValueError):
            read_sm(self.model(True)[:-1])
        model = self.model(False)[:-12] + struct.pack('<3I', 0, 1, 9)
        with self.assertRaises(ValueError):
            read_sm(model)

    def test_reject_unknown_vertex_format(self):
        model = bytearray(self.model(True))
        struct.pack_into('<I', model, 24, 99)
        with self.assertRaises(ValueError):
            read_sm(model)


if __name__ == '__main__':
    unittest.main()
