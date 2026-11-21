"""Overlay native exhaust origins/directions on a source review scene.

blender -b ship.blend --python this.py -- prepared.json output.png stern
Orange arrows are guides only; they are never exported to the fleet FBX.
"""
import json
import math
from pathlib import Path
import sys
import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from expanse_axes import blender_to_native
from create_expanse_project import GAMEPLAY_ENVELOPE

args = sys.argv[sys.argv.index('--') + 1:]
metadata_path, destination, view = Path(args[0]), args[1], args[2]
metadata = json.loads(metadata_path.read_text())
folder = metadata_path.parent
archive = np.load(folder / metadata['geometry'][0]['prepared_geometry'])
raw = [archive[str(i) + '_positions'] * metadata['unit_metres'] for i in range(int(archive['mesh_count']))]
extent = float(max(np.max([p.max(0) for p in raw], axis=0) - np.min([p.min(0) for p in raw], axis=0)))
scale = GAMEPLAY_ENVELOPE[metadata['workshop_id']] / extent
material = bpy.data.materials.new('ExhaustReviewGuide')
material.diffuse_color = (1, 0.14, 0.01, 1)
material.use_nodes = True
shader = material.node_tree.nodes.get('Principled BSDF')
shader.inputs['Base Color'].default_value = (1, 0.14, 0.01, 1)
shader.inputs['Emission Color'].default_value = (1, 0.08, 0.01, 1)
shader.inputs['Emission Strength'].default_value = 0.8
for number, pose in enumerate(json.loads((folder / 'drive-positions.json').read_text()), 1):
    origin = Vector(blender_to_native(np.array(pose[:3]) / scale))
    pitch, yaw = (math.radians(pose[3]), math.radians(pose[4])) if len(pose) == 6 else (0, 0)
    direction = Vector(blender_to_native((-math.cos(pitch) * math.cos(yaw),
                                         -math.cos(pitch) * math.sin(yaw), -math.sin(pitch))))
    length = extent * 0.07
    bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=extent * 0.008, radius2=0,
                                    depth=length, location=origin + direction * length / 2)
    arrow = bpy.context.object
    arrow.name = 'ReviewOnly_Exhaust_' + str(number)
    arrow.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
    arrow.data.materials.append(material)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=extent * 0.006, location=origin)
    bpy.context.object.data.materials.append(material)
sys.argv = [sys.argv[0], '--', destination, view]
exec(compile((Path(__file__).resolve().parent / 'render_expanse.py').read_text(), 'render_expanse.py', 'exec'))
