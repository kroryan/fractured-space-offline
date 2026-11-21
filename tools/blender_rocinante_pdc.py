"""Separate Rocinante's source PDC heads/barrels and preserve their hull mounts."""
import json
import math
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix
from expanse_axes import source_to_native, source_to_blender, blender_to_native, source_uv_to_blender

DYNAMIC_SECTIONS = set(range(23)) | {33}
# Servo, head, barrel and outward normal, read from the six original assemblies.
ASSEMBLIES = [
    (1, 2, 3, (0, -1, 0)), (6, 5, 4, (0, 1, 0)),
    (10, 9, 8, (-1, 0, 0)), (13, 14, 15, (1, 0, 0)),
    (17, 18, 19, (-1, 0, 0)), (22, 21, 20, (1, 0, 0)),
]


def make_piece(name, sections, archive, unit, basis, pivot, material):
    vertices, faces, normals = [], [], []
    offset = 0
    for section in sections:
        prefix = str(section) + '_'
        indices = archive[prefix + 'triangles']
        used, remapped = np.unique(indices, return_inverse=True)
        points = archive[prefix + 'positions'][used] * unit
        vertices.append(blender_to_native((points - pivot) @ basis))
        normals.append(blender_to_native(archive[prefix + 'normals'][used] @ basis))
        faces.append(remapped.reshape((-1, 3)) + offset)
        offset += len(points)
    points, faces, normals = np.concatenate(vertices), np.concatenate(faces), np.concatenate(normals)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(points.tolist(), [], faces.tolist())
    mesh.materials.append(material)
    mesh.update()
    # Preserve source UVs, including the original nozzle/PDC texture atlas.
    uv = source_uv_to_blender(np.concatenate([archive[str(i) + '_uv'][archive[str(i) + '_triangles'].ravel()] for i in sections]))
    mesh.uv_layers.new(name='UVMap').data.foreach_set('uv', uv.ravel())
    mesh.normals_split_custom_set_from_vertices(normals.tolist())
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def export_piece(obj, path, muzzle=None):
    bpy.ops.object.select_all(action='DESELECT')
    obj.hide_viewport = False
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    socket = None
    if muzzle is not None:
        socket = bpy.data.objects.new('SOCKET_Socket', None)
        bpy.context.collection.objects.link(socket)
        socket.parent = obj
        socket.location = blender_to_native(muzzle)
        # Socket local +X must follow the barrel after the measured FBX axis
        # conversion. An identity Blender empty imports with native yaw -90.
        socket.rotation_euler.z = -math.pi / 2
        socket.select_set(True)
    bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, object_types={'MESH', 'EMPTY'},
        apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS', mesh_smooth_type='FACE',
        bake_anim=False, axis_forward='-Y', axis_up='Z', path_mode='COPY', embed_textures=True)
    if socket is not None:
        bpy.data.objects.remove(socket, do_unlink=True)
    obj.select_set(False)
    obj.hide_render = True
    obj.hide_viewport = True


def prepare(metadata, output, materials):
    ident, unit = metadata['workshop_id'], metadata['unit_metres']
    archive = np.load(output / metadata['geometry'][0]['prepared_geometry'])
    raw = [archive[str(i) + '_positions'] * unit for i in range(int(archive['mesh_count']))]
    lower = np.min([p.min(0) for p in raw], axis=0)
    upper = np.max([p.max(0) for p in raw], axis=0)
    scale = 600 / float(max(upper - lower))
    templates, mounts = {}, []
    for number, (servo, head, barrel, outward) in enumerate(ASSEMBLIES):
        pivot = (raw[servo].min(0) + raw[servo].max(0)) / 2
        forward, up = np.array((0, 0, -1)), np.array(outward)
        basis = np.column_stack((forward, np.cross(forward, up), up))
        head_center = (raw[head].min(0) + raw[head].max(0)) / 2
        variant = 'Positive' if ((head_center - pivot) @ basis)[1] > 0 else 'Negative'
        # Proper rotation from the canonical turret frame to the ship frame.
        rotation = source_to_native(basis.T, ident).T
        quaternion = Matrix(rotation.tolist()).to_quaternion()
        mounts.append({'variant': variant, 'position': (source_to_native(pivot, ident) * scale).tolist(),
                       'quaternion': [quaternion.x, quaternion.y, quaternion.z, quaternion.w],
                       'source_servo_section': servo, 'source_head_section': head,
                       'source_barrel_section': barrel})
        if variant not in templates:
            # The two mirror variants preserve the original left/right designs.
            caps = (0, 1) if variant == 'Negative' else (6, 7)
            gun = make_piece('PDC_Rocinante_' + variant + '_Gun', [head, barrel], archive, unit, basis, pivot, materials[2])
            swivel = make_piece('PDC_Rocinante_' + variant + '_Swivel', caps, archive, unit, basis, pivot, materials[2])
            barrel_native = (raw[barrel] - pivot) @ basis
            muzzle = barrel_native.mean(0)
            muzzle[0] = barrel_native[:, 0].max()
            export_piece(gun, output / (gun.name + '.fbx'), muzzle)
            export_piece(swivel, output / (swivel.name + '.fbx'))
            templates[variant] = (gun, swivel)
        # Assemble source-mount instances in the review scene as well.
        conversion = np.array(((0, -1, 0), (-1, 0, 0), (0, 0, 1)))
        rotation_blender = Matrix((conversion @ rotation @ conversion).tolist()).to_4x4()
        translation = Matrix.Translation(source_to_blender(pivot, ident).tolist())
        for template in templates[variant]:
            instance = bpy.data.objects.new('PDC_Mount_' + str(number) + '_' + template.name, template.data)
            bpy.context.collection.objects.link(instance)
            instance.matrix_world = translation @ rotation_blender
    bpy.ops.object.select_all(action='DESELECT')
    (output / 'pdc-rig.json').write_text(json.dumps({'mounts': mounts, 'scale': scale,
        'removed_hull_sections': sorted(DYNAMIC_SECTIONS), 'templates': list(templates)}, indent=2) + '\n')
    return DYNAMIC_SECTIONS
