"""Diagnostic color-only source-atlas render; never exports production assets."""
import bpy
from pathlib import Path
import sys

args = sys.argv[sys.argv.index('--') + 1:]
for material in bpy.data.materials:
    if not material.use_nodes:
        continue
    shader = material.node_tree.nodes.get('Principled BSDF')
    if shader:
        for link in list(shader.inputs['Normal'].links):
            material.node_tree.links.remove(link)
        shader.inputs['Roughness'].default_value = 1
        shader.inputs['Metallic'].default_value = 0
if args[1] == 'flip-v':
    for mesh in bpy.data.meshes:
        for layer in mesh.uv_layers:
            for point in layer.data:
                point.uv.y = 1 - point.uv.y
sys.argv = [sys.argv[0], '--', args[0], 'front']
exec(compile((Path(__file__).resolve().parent / 'render_expanse.py').read_text(), 'render_expanse.py', 'exec'))
