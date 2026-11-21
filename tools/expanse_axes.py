"""Source frames and measured Blender-to-UE4.19 FBX conversion.

The asymmetric calibration fixture proves that -Y-forward FBX export followed
by UE4.19 ForceFrontXAxis imports Blender (x,y,z) as UE (-y,-x,z).
Keep geometry, mounts, effects and armour regions on this same measured frame.
"""
import numpy as np

SOURCE_FORWARD = {
    '2211361535': (0, 0, -1), '2224316655': (0, 0, 1),
    '2368610280': (0, 0, 1), '2375119898': (0, 0, 1),
    '2375181309': (-1, 0, 0), '2687045417': (-1, 0, 0),
    '2687094193': (-1, 0, 0),
}


def source_to_native(points, ident):
    forward = np.asarray(SOURCE_FORWARD[ident], dtype=float)
    up = np.array((0, 1, 0), dtype=float)
    return np.asarray(points) @ np.column_stack((forward, np.cross(forward, up), up))


def blender_to_native(points):
    return np.asarray(points)[..., [1, 0, 2]] * np.array((-1, -1, 1))


def source_to_blender(points, ident):
    # The measured conversion is its own inverse.
    return blender_to_native(source_to_native(points, ident))


def source_uv_to_blender(values):
    """SpaceEngine's atlas V origin is at the top; Blender's is at the bottom."""
    result = np.asarray(values).copy()
    result[..., 1] = 1 - result[..., 1]
    return result
