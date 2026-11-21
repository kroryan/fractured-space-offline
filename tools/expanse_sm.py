"""Read the SM02 variants found in the reviewed SpaceEngine ship packages.

This is an asset preparation tool, not a Fractured Space runtime loader.
NumPy is required only on the authoring machine. Converted output is staged in obj/.
The packed layout was inferred from the local files; visual round-trip validation
is required before any converted geometry is accepted for distribution.
"""
from dataclasses import dataclass
import struct
import numpy as np


@dataclass
class Mesh:
    material: int
    positions: np.ndarray
    normals: np.ndarray
    uv: np.ndarray
    triangles: np.ndarray
    repaired_normals: int = 0
    degenerate_triangles_removed: int = 0


def snorm(values, maximum):
    return np.maximum(values.astype(np.float32) / maximum, -1.0)


def packed_normal(words):
    components = []
    for shift in (0, 10, 20):
        value = ((words >> shift) & 1023).astype(np.int32)
        value[value > 511] -= 1024
        components.append(snorm(value, 511))
    result = np.column_stack(components)
    length = np.linalg.norm(result, axis=1)
    if np.any((length > 0.01) & (length < 0.5)) or np.any(length > 1.1):
        raise ValueError('Packed normals outside the validated range')
    return result / np.maximum(length[:, None], 1e-12)


def read_sm(data):
    if len(data) < 28 or data[:4] != b'SM02':
        raise ValueError('Expected an SM02 model')
    count = struct.unpack_from('<I', data, 4)[0]
    encoding = struct.unpack_from('<I', data, 24)[0]
    if encoding not in (0, 4) or not 0 < count < 100000:
        raise ValueError('Unsupported SM02 vertex encoding or mesh count')
    stride = 48 if encoding == 0 else 20
    offset, meshes = 28, []
    for _ in range(count):
        if offset + 40 > len(data):
            raise ValueError('Truncated mesh header')
        vertices, indices, material, mode = struct.unpack_from('<IIHH', data, offset)
        transform = np.array(struct.unpack_from('<7f', data, offset + 12), dtype=np.float32)
        if mode != 0 or not vertices or indices % 3 or not np.isfinite(transform).all():
            raise ValueError('Only finite triangle meshes are supported')
        offset += 40
        end = offset + vertices * stride + indices * 4
        if end > len(data):
            raise ValueError('Truncated mesh data')
        if encoding == 0:
            values = np.frombuffer(data, dtype='<f4', count=vertices * 12, offset=offset).reshape(vertices, 12)
            positions, normals, uv = values[:, :3].copy(), values[:, 3:6].copy(), values[:, 10:12].copy()
        else:
            # Four shorts reserve eight position bytes; the fourth is unused.
            # The normal/tangent are signed 10:10:10:2; UV uses signed shorts.
            layout = np.dtype({'names': ['pos', 'normal', 'tangent', 'uv'],
                               'formats': [('<i2', 4), '<u4', '<u4', ('<i2', 2)],
                               'offsets': [0, 8, 12, 16], 'itemsize': 20})
            values = np.frombuffer(data, dtype=layout, count=vertices, offset=offset)
            positions = snorm(values['pos'][:, :3], 32767) * transform[3] + transform[:3]
            normals = packed_normal(values['normal'])
            uv = snorm(values['uv'], 32767) * transform[6] + transform[4:6]
        triangles = np.frombuffer(data, dtype='<u4', count=indices, offset=offset + vertices * stride).reshape(-1, 3).copy()
        if (triangles.size and triangles.max() >= vertices) or not all(np.isfinite(v).all() for v in (positions, normals, uv)):
            raise ValueError('Invalid index or non-finite vertex data')
        invalid = np.linalg.norm(normals, axis=1) < 0.5
        repaired, removed = int(invalid.sum()), 0
        if repaired:
            affected = invalid[triangles].any(axis=1)
            adjacent = triangles[affected]
            face_normals = np.cross(positions[adjacent[:, 1]] - positions[adjacent[:, 0]], positions[adjacent[:, 2]] - positions[adjacent[:, 0]])
            usable = np.linalg.norm(face_normals, axis=1) > 1e-12
            remove_mask = np.zeros(len(triangles), dtype=bool)
            remove_mask[np.flatnonzero(affected)[~usable]] = True
            removed = int(remove_mask.sum())
            sums = np.zeros_like(normals)
            for corner in range(3):
                np.add.at(sums, adjacent[usable, corner], face_normals[usable])
            lengths = np.linalg.norm(sums, axis=1)
            repairable = invalid & (lengths > 1e-12)
            normals[repairable] = sums[repairable] / lengths[repairable, None]
            # Any remaining zero-normal vertices are unreferenced after removing
            # their degenerate triangles; their placeholder normal is not rendered.
            normals[invalid & ~repairable] = (0, 0, 1)
            triangles = triangles[~remove_mask]
        meshes.append(Mesh(material, positions, normals, uv, triangles, repaired, removed))
        offset = end
    if offset != len(data):
        raise ValueError('Unexpected trailing bytes in SM02 model')
    return meshes


def save_npz(meshes, destination):
    arrays = {}
    for index, mesh in enumerate(meshes):
        for field in ('positions', 'normals', 'uv', 'triangles'):
            arrays[str(index) + '_' + field] = getattr(mesh, field)
        arrays[str(index) + '_material'] = np.array(mesh.material)
    arrays['mesh_count'] = np.array(len(meshes))
    np.savez(destination, **arrays)
