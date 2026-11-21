"""Run: blender -b -t 4 --python-exit-code 1 --python tools/blender_expanse.py -- <prepared.json>

Builds a review scene and FBX from locally prepared geometry. Outputs stay in obj/.
Nothing produced by this script is considered release-ready without visual and
game validation. Television audio is never imported.
"""
import bpy
import json
import math
import os
from pathlib import Path
import re
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from expanse_axes import SOURCE_FORWARD, source_to_blender, source_uv_to_blender


def material_definitions(root):
    result = {}
    for file in root.rglob('*.sml'):
        text = file.read_text(encoding='utf-8-sig', errors='replace')
        for name, body in re.findall(r'Material\s+"([^"]+)"\s*\{([^}]+)\}', text, re.S):
            result[name] = body
    return result


def texture_file(root, name):
    # SpaceEngine texture paths are relative to textures/spacecraft, with optional wildcards.
    # The reviewed Razorback library contains this duplicated path and stale
    # filename. Resolve it explicitly to the texture supplied by the same mod.
    aliases = {'The_Expanse/Razorback/The_Expanse/Razorback/lights.*': 'The_Expanse/Razorback/rzr_lights.png'}
    name = aliases.get(name, name)
    candidates = []
    for base in root.rglob('spacecraft'):
        if base.parent.name.lower() != 'textures':
            continue
        candidates.extend(base.glob(name))
    return next((p for p in sorted(candidates) if p.is_file()), None)


def create_material(root, name, definition, texture_restricted):
    material = bpy.data.materials.new(re.sub(r'[^A-Za-z0-9_]', '_', name))
    material.use_nodes = True
    shader = material.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (0.25, 0.28, 0.32, 1)
    shader.inputs['Roughness'].default_value = 0.4
    material['source_material'] = name
    if texture_restricted:
        material['review_note'] = 'Original neutral material; mod texture redistribution rights unresolved.'
        return material
    color = re.search(r'^\s*DiffColor\s+\(([^)]+)\)', definition, re.M)
    if color:
        components = [float(x) for x in color.group(1).split()]
        if len(components) == 3:
            shader.inputs['Base Color'].default_value = tuple(components) + (1,)
    power = re.search(r'^\s*SpecPower\s+([0-9.eE+-]+)', definition, re.M)
    if power:
        shader.inputs['Roughness'].default_value = max(0.08, min(0.9, math.sqrt(2 / (float(power.group(1)) + 2))))
    nodes, links = material.node_tree.nodes, material.node_tree.links
    for key, socket, noncolor in [('DiffMap', 'Base Color', False), ('NormMap', 'Normal', True), ('EmisMap', 'Emission Color', False)]:
        match = re.search(r'^\s*' + key + r'\s+"([^"]+)"', definition, re.M)
        if not match:
            continue
        path = texture_file(root, match.group(1))
        if path is None:
            raise RuntimeError('Missing licensed source texture: ' + match.group(1))
        image = bpy.data.images.load(str(path.resolve()), check_existing=True)
        if noncolor:
            image.colorspace_settings.name = 'Non-Color'
        node = nodes.new('ShaderNodeTexImage')
        node.image = image
        if key == 'NormMap':
            normal = nodes.new('ShaderNodeNormalMap')
            links.new(node.outputs['Color'], normal.inputs['Color'])
            links.new(normal.outputs['Normal'], shader.inputs['Normal'])
        else:
            links.new(node.outputs['Color'], shader.inputs[socket])
            if key == 'DiffMap' and re.search(r'DiffMapAlpha\s+"Transp"', definition):
                links.new(node.outputs['Alpha'], shader.inputs['Alpha'])
                material.surface_render_method = 'DITHERED'
            if key == 'EmisMap':
                shader.inputs['Emission Strength'].default_value = 1
    return material


def main():
    args = sys.argv[sys.argv.index('--') + 1:]
    metadata_path = Path(args[0]).resolve()
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    output = metadata_path.parent
    source = output / 'source'
    asset_name = re.sub(r'[^A-Za-z0-9_]', '_', metadata['display_name'])
    triangle_budget = int(os.environ.get('EXPANSE_TRIANGLE_BUDGET', '0'))
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    definitions = material_definitions(source)
    materials = [create_material(source, name, definitions.get(name, ''), metadata['yacht_texture_restriction']) for name in metadata['materials']]
    omitted_sections = set()
    omitted_faces = {}
    source_overrides, torpedo_rig = {}, None
    if metadata['workshop_id'] == '2211361535':
        from blender_rocinante_pdc import prepare
        omitted_sections = prepare(metadata, output, materials)
        from blender_rocinante_torpedoes import prepare as prepare_torpedoes
        source_overrides, torpedo_rig = prepare_torpedoes(metadata, output)
    if metadata['workshop_id'] == '2375119898':
        from blender_donnager_railguns import prepare
        omitted_faces = prepare(metadata, output, materials)
    if metadata['workshop_id'] == '2224316655':
        from blender_razorback_weapon import prepare
        prepare(metadata, output, materials)
    if metadata['workshop_id'] == '2687045417':
        from blender_mayotte_weapons import prepare
        omitted_sections = prepare(metadata, output, materials)
    if metadata['workshop_id'] in ('2687094193', '2375181309'):
        from blender_escort_weapons import prepare
        omitted_sections = prepare(metadata, output, materials)
    for item in metadata['geometry']:
        archive = np.load(output / item['prepared_geometry'])
        positions, normals, uv, triangles, material_indices = [], [], [], [], []
        vertex_offset = 0
        for i in range(int(archive['mesh_count'])):
            if i in omitted_sections:
                continue
            prefix = str(i) + '_'
            vertices = source_overrides.get(i, {}).get('positions', archive[prefix + 'positions'])
            faces = archive[prefix + 'triangles']
            if i in omitted_faces:
                faces = faces[~omitted_faces[i]]
            positions.append(vertices)
            normals.append(source_overrides.get(i, {}).get('normals', archive[prefix + 'normals']))
            uv.append(archive[prefix + 'uv'])
            triangles.append(faces + vertex_offset)
            material_indices.append(np.full(len(faces), int(archive[prefix + 'material']), dtype=np.int32))
            vertex_offset += len(vertices)
        positions = np.concatenate(positions) * metadata['unit_metres']
        normals = np.concatenate(normals)
        uv, triangles = source_uv_to_blender(np.concatenate(uv)), np.concatenate(triangles)
        material_indices = np.concatenate(material_indices)
        positions = source_to_blender(positions, metadata['workshop_id'])
        normals = source_to_blender(normals, metadata['workshop_id'])
        loop_uv = uv[triangles.ravel()]
        loop_normals = normals[triangles.ravel()]
        # SM02 stores triangle soup with duplicated positions. Weld positions
        # before collapse reduction; UVs and hard normals remain per-loop.
        # Reducing disconnected triangles can delete faces rather than simplify
        # a continuous surface, so it is not a valid runtime LOD operation.
        positions, welded = np.unique(positions, axis=0, return_inverse=True)
        triangles = welded[triangles].astype(np.int32)
        valid = ((triangles[:, 0] != triangles[:, 1]) & (triangles[:, 1] != triangles[:, 2]) &
                 (triangles[:, 0] != triangles[:, 2]))
        loop_uv = loop_uv.reshape((-1, 3, 2))[valid].reshape((-1, 2))
        loop_normals = loop_normals.reshape((-1, 3, 3))[valid].reshape((-1, 3))
        material_indices = material_indices[valid]
        triangles = triangles[valid]
        mesh = bpy.data.meshes.new(asset_name)
        mesh.vertices.add(len(positions))
        mesh.vertices.foreach_set('co', positions.ravel())
        mesh.loops.add(triangles.size)
        mesh.loops.foreach_set('vertex_index', triangles.ravel())
        mesh.polygons.add(len(triangles))
        mesh.polygons.foreach_set('loop_start', np.arange(len(triangles), dtype=np.int32) * 3)
        mesh.polygons.foreach_set('loop_total', np.full(len(triangles), 3, dtype=np.int32))
        mesh.polygons.foreach_set('material_index', material_indices)
        mesh.polygons.foreach_set('use_smooth', np.ones(len(triangles), dtype=bool))
        layer = mesh.uv_layers.new(name='UVMap')
        layer.data.foreach_set('uv', loop_uv.ravel())
        for material in materials:
            mesh.materials.append(material)
        mesh.update(calc_edges=True)
        mesh.normals_split_custom_set(loop_normals.tolist())
        obj = bpy.data.objects.new(asset_name, mesh)
        bpy.context.collection.objects.link(obj)
        obj['source_workshop_id'] = metadata['workshop_id']
        obj['source_credit'] = metadata['source_credit']
        obj['release_ready'] = False
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        if torpedo_rig is not None:
            from blender_rocinante_torpedoes import open_bays
            open_bays(obj, torpedo_rig, metadata['workshop_id'])
        if triangle_budget and len(mesh.polygons) > triangle_budget:
            # UE4.19's automatic reduction can reserve several gigabytes for a
            # multi-million-triangle import. Decimate before export instead so
            # the editor receives a bounded, distributable runtime mesh. The
            # modifier preserves material boundaries for the imported sections.
            reduction = obj.modifiers.new('AuthoringRuntimeReduction', 'DECIMATE')
            reduction.ratio = max(0.002, triangle_budget / len(mesh.polygons))
            bpy.ops.object.modifier_apply(modifier=reduction.name)
            print('Reduced', asset_name, 'to', len(obj.data.polygons), 'triangles', flush=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1
    bpy.ops.wm.save_as_mainfile(filepath=str(output / (asset_name + '.blend')))
    bpy.ops.export_scene.fbx(filepath=str(output / (asset_name + '.fbx')), use_selection=True,
                             object_types={'MESH'}, apply_unit_scale=True,
                             apply_scale_options='FBX_SCALE_UNITS', mesh_smooth_type='FACE',
                             add_leaf_bones=False, bake_anim=False, axis_forward='-Y', axis_up='Z',
                             path_mode='COPY', embed_textures=True)
    # Native LocationalCollisionMeshComponent addresses six armour material
    # regions. Never feed it the visual mesh's unrelated texture/material IDs.
    collision_name = 'SM_ARM_EXP_' + asset_name
    collision = obj.copy()
    collision.data = obj.data.copy()
    collision.name = collision_name
    collision.data.name = collision_name
    bpy.context.collection.objects.link(collision)
    collision.data.materials.clear()
    for region in ('Front', 'Rear', 'Left', 'Right', 'Top', 'Bottom'):
        collision.data.materials.append(bpy.data.materials.new('Armour_' + region))
    for face in collision.data.polygons:
        normal = face.normal
        axis = max(range(3), key=lambda value: abs(normal[value]))
        # Calibrated Blender -Y forward, -X right, +Z up. Indices are explicit so the
        # six native locational-health entries remain independent.
        face.material_index = ((0 if normal.y < 0 else 1) if axis == 1 else
                               (3 if normal.x < 0 else 2) if axis == 0 else
                               (4 if normal.z >= 0 else 5))
    bpy.ops.object.select_all(action='DESELECT')
    collision.select_set(True)
    bpy.context.view_layer.objects.active = collision
    bpy.ops.export_scene.fbx(filepath=str(output / (collision_name + '.fbx')), use_selection=True,
                             object_types={'MESH'}, apply_unit_scale=True,
                             apply_scale_options='FBX_SCALE_UNITS', mesh_smooth_type='FACE',
                             add_leaf_bones=False, bake_anim=False, axis_forward='-Y', axis_up='Z')
    (output / 'export-result.json').write_text(json.dumps({'display_name': metadata['display_name'],
                                                         'fbx': asset_name + '.fbx',
                                                         'blend': asset_name + '.blend',
                                                         'triangle_budget': triangle_budget,
                                                         'source_forward': SOURCE_FORWARD[metadata['workshop_id']],
                                                         'triangle_count': len(obj.data.polygons),
                                                         'armour_fbx': collision_name + '.fbx',
                                                         'release_ready': False}, indent=2), encoding='utf-8')
    print('Prepared review scene and FBX:', asset_name, flush=True)


if __name__ == '__main__':
    main()
