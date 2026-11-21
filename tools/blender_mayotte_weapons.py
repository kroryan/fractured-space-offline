"""Articulate Mayotte's 42 original PDCs and two original railguns."""
import json
import bpy
import numpy as np
from mathutils import Matrix
from blender_rocinante_pdc import make_piece, export_piece
from expanse_axes import source_to_native, source_to_blender


def center(points):
    return (points.min(0) + points.max(0)) / 2


def reduce_piece(obj, budget):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.00001)
    bpy.ops.object.mode_set(mode='OBJECT')
    if len(obj.data.polygons) > budget:
        modifier = obj.modifiers.new('WeaponRuntimeReduction', 'DECIMATE')
        modifier.ratio = budget / len(obj.data.polygons)
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    obj.select_set(False)


def instance(template, name, pivot, rotation, ident):
    conversion = np.array(((0, -1, 0), (-1, 0, 0), (0, 0, 1)))
    obj = bpy.data.objects.new(name, template.data)
    bpy.context.collection.objects.link(obj)
    obj.matrix_world = Matrix.Translation(source_to_blender(pivot, ident).tolist()) @ Matrix(
        (conversion @ rotation @ conversion).tolist()).to_4x4()


def prepare(metadata, output, materials):
    ident, unit = metadata['workshop_id'], metadata['unit_metres']
    archive = np.load(output / metadata['geometry'][0]['prepared_geometry'])
    raw = [archive[str(i) + '_positions'].astype(np.float64) * unit for i in range(int(archive['mesh_count']))]
    scale = 1200 / float(max(np.max([p.max(0) for p in raw], axis=0) -
                               np.min([p.min(0) for p in raw], axis=0)))
    spheres = [i for i in range(len(raw)) if int(archive[str(i) + '_material']) == 16
               and len(archive[str(i) + '_triangles']) == 10390]
    if len(spheres) != 42:
        raise ValueError('Mayotte source PDC inventory changed')
    reference_pivot = center(raw[495])
    up = np.array((0, -1, 1), dtype=float); up /= np.linalg.norm(up)
    forward = np.array((-1, 0, 0))
    basis = np.column_stack((forward, np.cross(forward, up), up))
    gun = make_piece('PDC_Mayotte_Gun', [496, 497, 498], archive, unit, basis,
                     reference_pivot, materials[16])
    swivel = make_piece('PDC_Mayotte_Swivel', [495], archive, unit, basis,
                        reference_pivot, materials[16])
    barrel = (raw[496] - reference_pivot) @ basis
    muzzle = barrel.mean(0); muzzle[0] = barrel[:, 0].max()
    reduce_piece(gun, 8000); reduce_piece(swivel, 2000)
    export_piece(gun, output / (gun.name + '.fbx'), muzzle)
    export_piece(swivel, output / (swivel.name + '.fbx'))
    reference = np.concatenate([raw[i] for i in (495, 496, 497, 498)])
    centroid = reference.mean(0)
    centered = reference - centroid
    omitted, mounts = set(), []
    for sphere in spheres:
        sections = [sphere, sphere + 1, sphere + 2, sphere + 3]
        target = np.concatenate([raw[i] for i in sections])
        target_centroid = target.mean(0)
        left, singular, right = np.linalg.svd(centered.T @ (target - target_centroid))
        row_rotation = left @ right
        if np.linalg.det(row_rotation) < 0.999:
            raise ValueError('A Mayotte PDC requires a mirrored mesh variant')
        error = np.linalg.norm(centered @ row_rotation + target_centroid - target, axis=1)
        if error.max() > 0.06:
            raise ValueError('Mayotte PDC does not match the source template: ' + str(sphere))
        pivot = (reference_pivot - centroid) @ row_rotation + target_centroid
        rotation = source_to_native((row_rotation.T @ basis).T, ident).T
        quaternion = Matrix(rotation.tolist()).to_quaternion()
        mounts.append({'source_sections': sections, 'position': (source_to_native(pivot, ident) * scale).tolist(),
            'quaternion': [quaternion.x, quaternion.y, quaternion.z, quaternion.w],
            'source_fit_max_error_metres': float(error.max())})
        omitted.update(sections)
        for template in (gun, swivel):
            instance(template, 'PDC_Mount_' + str(sphere) + '_' + template.name, pivot, rotation, ident)
    rails = []
    for side, base, head, barrel_section, cap, light_a, light_b, normal in [
        ('Dorsal', 755, 756, 760, 758, 757, 759, (0, 1, 0)),
        ('Ventral', 761, 762, 766, 764, 763, 765, (0, -1, 0))]:
        up = np.array(normal)
        basis = np.column_stack((forward, np.cross(forward, up), up))
        yaw_pivot, pitch_pivot = center(raw[base]), center(raw[head])
        rotation = source_to_native(basis.T, ident).T
        quaternion = Matrix(rotation.tolist()).to_quaternion()
        for suffix, sections, pivot in [('Swivel', [head, cap, light_a, light_b], yaw_pivot),
                                         ('Gun', [barrel_section], pitch_pivot)]:
            # The lights are separate material sections, so preserve their
            # original material assignment rather than assigning the gun atlas.
            name = 'Railgun_Mayotte_' + side + '_' + suffix
            pieces = []
            for section in sections:
                piece = make_piece(name + '_' + str(section), [section], archive, unit, basis, pivot,
                                   materials[int(archive[str(section) + '_material'])])
                pieces.append(piece)
            bpy.ops.object.select_all(action='DESELECT')
            for piece in pieces:
                piece.select_set(True)
            bpy.context.view_layer.objects.active = pieces[0]
            bpy.ops.object.join()
            obj = pieces[0]; obj.name = name
            muzzle = None
            if suffix == 'Gun':
                local = (raw[barrel_section] - pivot) @ basis
                muzzle = local.mean(0); muzzle[0] = local[:, 0].max()
            export_piece(obj, output / (name + '.fbx'), muzzle)
            instance(obj, 'Railgun_Mount_' + side + '_' + suffix, pivot, rotation, ident)
            omitted.update(sections)
        rails.append({'side': side, 'position': (source_to_native(yaw_pivot, ident) * scale).tolist(),
            'quaternion': [quaternion.x, quaternion.y, quaternion.z, quaternion.w],
            'gun_relative_location': (((pitch_pivot - yaw_pivot) @ basis) * scale).tolist(),
            'muzzle_local': (muzzle * scale).tolist()})
    bpy.ops.object.select_all(action='DESELECT')
    (output / 'weapon-rig.json').write_text(json.dumps({'pdc_mounts': mounts, 'railgun_mounts': rails,
        'omitted_hull_sections': sorted(omitted), 'scale': scale,
        'requires_gameplay_validation': True}, indent=2) + '\n')
    return omitted
