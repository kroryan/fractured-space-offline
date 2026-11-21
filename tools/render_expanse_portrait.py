"""Render the actual adapted ship with vanilla-style framing and transparency.

Run with its review .blend loaded. Output contains the six filenames expected
by the native selector, drafting, store and mastery-card views.
"""
import json
import math
from pathlib import Path
import sys
import bpy
import numpy as np
from mathutils import Vector, Quaternion

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_expanse_fleet import stable_guid

args = sys.argv[sys.argv.index('--') + 1:]
slug = args[0]
root = Path(__file__).resolve().parents[1]
destination = root / 'obj/expanse-authoring/portraits' / stable_guid(slug, 'ship')
destination.mkdir(parents=True, exist_ok=True)
objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH' and not obj.hide_render]
corners = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
lower = Vector(tuple(min(point[i] for point in corners) for i in range(3)))
upper = Vector(tuple(max(point[i] for point in corners) for i in range(3)))
center, size = (lower + upper) / 2, max(upper - lower)
bpy.ops.object.camera_add(location=center + Vector((1, -0.38, 0.38)).normalized() * size * 2.5)
camera = bpy.context.object
rotation = (center - camera.location).to_track_quat('-Z', 'Y')
forward = rotation.inverted() @ Vector((0, -1, 0))
roll = math.atan2(forward.y, forward.x) - math.radians(170)
rotation = rotation @ Quaternion(Vector((0, 0, 1)), roll)
camera.rotation_mode = 'QUATERNION'; camera.rotation_quaternion = rotation
camera.data.type = 'ORTHO'; camera.data.clip_end = size * 20
projected = []
view_rotation = np.array(rotation.inverted().to_matrix())
for obj in objects:
    vertices = np.empty(len(obj.data.vertices) * 3, dtype=np.float32)
    obj.data.vertices.foreach_get('co', vertices)
    transform = np.array(obj.matrix_world)
    world = vertices.reshape((-1, 3)) @ transform[:3, :3].T + transform[:3, 3]
    projected.append((world - np.array(center)) @ view_rotation.T)
projected = np.concatenate(projected)
left, right = float(projected[:, 0].min()), float(projected[:, 0].max())
bottom, top = float(projected[:, 1].min()), float(projected[:, 1].max())
camera.location += rotation @ Vector(((left + right) / 2, (bottom + top) / 2, 0))
scene = bpy.context.scene
scene.camera = camera
for direction, energy, color in [((1, -1, 2), 3.2, (1, 0.94, 0.87)),
                                  ((-1, 1, 0.8), 2.0, (0.65, 0.8, 1)),
                                  ((1, 1, -0.2), 1.2, (0.8, 0.88, 1))]:
    bpy.ops.object.light_add(type='SUN', location=center + Vector(direction) * size)
    light = bpy.context.object
    light.rotation_euler = (center - light.location).to_track_quat('-Z', 'Y').to_euler()
    light.data.energy = energy; light.data.color = color
scene.world.use_nodes = True
scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value = 0.35
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.film_transparent = True
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.resolution_percentage = 100
for name, width, height in [('large', 1631, 652), ('main', 464, 207), ('store', 464, 207),
                            ('bronze', 278, 124), ('silver', 278, 124), ('gold', 278, 124)]:
    camera.data.ortho_scale = max(right - left, (top - bottom) * width / height) * 1.09
    scene.render.resolution_x, scene.render.resolution_y = width, height
    scene.render.filepath = str(destination / (name + '.png'))
    bpy.ops.render.render(write_still=True)
(destination / 'portrait.json').write_text(json.dumps({'ship_guid': stable_guid(slug, 'ship'),
    'source_scene': bpy.data.filepath, 'background': 'transparent', 'source': 'adapted playable ship geometry',
    'files': ['main.png', 'store.png', 'large.png', 'bronze.png', 'silver.png', 'gold.png']}, indent=2) + '\n')
print('Rendered native selector portraits:', slug)
