"""Blender-only asymmetric coordinate fixture for measuring the UE FBX transform."""
import bpy
from pathlib import Path
import sys

destination = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
mesh = bpy.data.meshes.new('AxisCalibration')
mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 2, 0), (0, 0, 3)], [],
                 [(0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3)])
mesh.update()
obj = bpy.data.objects.new('AxisCalibration', mesh)
bpy.context.collection.objects.link(obj)
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = 1
bpy.ops.export_scene.fbx(filepath=str(destination), use_selection=True, object_types={'MESH'},
                         apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
                         mesh_smooth_type='FACE', bake_anim=False, axis_forward='-Y', axis_up='Z')
