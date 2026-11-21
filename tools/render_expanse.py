"""Blender review render: blender -b <ship.blend> --python tools/render_expanse.py -- <output.png>"""
import bpy
from mathutils import Vector
import sys
from pathlib import Path

args = sys.argv[sys.argv.index('--') + 1:]
if not Path(args[0]).is_absolute():
    raise ValueError('Pass an absolute render destination; Blender may change its working directory.')
objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH' and not obj.hide_render]
corners = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
lower = Vector(tuple(min(p[i] for p in corners) for i in range(3)))
upper = Vector(tuple(max(p[i] for p in corners) for i in range(3)))
center = (lower + upper) / 2
size = max(upper - lower)
views = {'front': (1, -1.4, 0.85), 'rear': (-1, 1.4, 0.85),
         'side': (1, 0, 0.1), 'left': (-1, -0.3, 0.2),
         'bow': (0, -1, 0), 'stern': (0, 1, 0), 'bottom': (0.05, 0, -1), 'top': (0.05, 0, 1)}
view = args[1] if len(args) > 1 else 'front'
if len(args) > 2:
    center = Vector(tuple(float(value) for value in args[2].split(',')))
    size = float(args[3])
bpy.ops.object.camera_add(location=center + Vector(views[view]).normalized() * size * 1.7)
camera = bpy.context.object
camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = size * 1.18
camera.data.clip_end = size * 20
bpy.context.scene.camera = camera
for direction, energy in [((1, -1, 2), 3.0), ((-1, 1, 0.5), 1.5)]:
    bpy.ops.object.light_add(type='SUN', location=center + Vector(direction) * size)
    light = bpy.context.object
    light.rotation_euler = (center - light.location).to_track_quat('-Z', 'Y').to_euler()
    light.data.energy = energy
world = bpy.context.scene.world
world.use_nodes = True
world.node_tree.nodes.get('Background').inputs['Color'].default_value = (0.06, 0.08, 0.12, 1)
world.node_tree.nodes.get('Background').inputs['Strength'].default_value = 0.5
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 1600
scene.render.resolution_y = 1200
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = args[0]
scene.render.film_transparent = False
bpy.ops.render.render(write_still=True)
print('Review bounds (metres):', tuple(upper - lower))
