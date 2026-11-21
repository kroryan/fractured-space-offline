"""Separate Avalanche and Chariot's original two cannon assemblies per hull."""
import json
import bpy
import numpy as np
from mathutils import Matrix
from blender_rocinante_pdc import make_piece, export_piece
from blender_mayotte_weapons import center, reduce_piece, instance
from expanse_axes import source_to_native


def prepare(metadata, output, materials):
    ident, unit = metadata['workshop_id'], metadata['unit_metres']
    archive = np.load(output / metadata['geometry'][0]['prepared_geometry'])
    raw = [archive[str(i) + '_positions'].astype(np.float64) * unit for i in range(int(archive['mesh_count']))]
    avalanche = ident == '2687094193'
    title = 'Avalanche' if avalanche else 'Chariot'
    envelope = 700 if avalanche else 350
    scale = envelope / float(max(np.max([p.max(0) for p in raw], axis=0) -
                                    np.min([p.min(0) for p in raw], axis=0)))
    if avalanche:
        assemblies = [
            ('Port', 24, 26, [25, 28] + list(range(318, 325)), [26], (-1, 0, 0), (0, 0, -1)),
            ('Starboard', 336, 338, [337, 340] + list(range(630, 637)), [338], (-1, 0, 0), (0, 0, 1))]
        omitted = set()
    else:
        assemblies = [
            ('Aft', 283, 304, [i for i in range(282, 305) if i not in (283, 302)], [302], (1, 0, 0), (0, 1, 0)),
            ('Fore', 307, 328, [i for i in range(306, 329) if i not in (307, 326)], [326], (-1, 0, 0), (0, 1, 0))]
        # Source contains coincident copies of both guns. Keep only the more
        # complete second assemblies and one pair of their fixed pedestals.
        omitted = set(range(125, 174))
    mounts = []
    for side, base, pitch, gun_sections, swivel_sections, forward, up in assemblies:
        forward, up = np.array(forward), np.array(up)
        basis = np.column_stack((forward, np.cross(forward, up), up))
        yaw_pivot, pitch_pivot = center(raw[base]), center(raw[pitch])
        rotation = source_to_native(basis.T, ident).T
        quaternion = Matrix(rotation.tolist()).to_quaternion()
        barrel_section = gun_sections[0]
        for suffix, sections, pivot, budget in [('Gun', gun_sections, pitch_pivot, 18000 if avalanche else 6000),
                                                ('Swivel', swivel_sections, yaw_pivot, 6000 if avalanche else 2000)]:
            name = 'Cannon_' + title + '_' + side + '_' + suffix
            pieces = []
            for section in sections:
                obj = make_piece(name + '_' + str(section), [section], archive, unit, basis, pivot,
                                 materials[int(archive[str(section) + '_material'])])
                pieces.append(obj)
            bpy.ops.object.select_all(action='DESELECT')
            for obj in pieces:
                obj.select_set(True)
            bpy.context.view_layer.objects.active = pieces[0]
            bpy.ops.object.join()
            obj = pieces[0]; obj.name = name
            muzzle = None
            if suffix == 'Gun':
                local = (raw[barrel_section] - pitch_pivot) @ basis
                muzzle = local.mean(0); muzzle[0] = local[:, 0].max()
                if not avalanche:
                    # Chariot's first section contains the barrel AND receiver.
                    # Derive the bore centre only from the actual tip plane.
                    tip = local[local[:, 0] > local[:, 0].max() - 0.015]
                    muzzle[1:] = (tip[:, 1:].min(0) + tip[:, 1:].max(0)) / 2
            reduce_piece(obj, budget)
            export_piece(obj, output / (name + '.fbx'), muzzle)
            instance(obj, 'Cannon_Mount_' + side + '_' + suffix, pivot, rotation, ident)
            omitted.update(sections)
        # Muzzle refers to the gun part, not the last (swivel) loop iteration.
        local = (raw[barrel_section] - pitch_pivot) @ basis
        muzzle = local.mean(0); muzzle[0] = local[:, 0].max()
        if not avalanche:
            tip = local[local[:, 0] > local[:, 0].max() - 0.015]
            muzzle[1:] = (tip[:, 1:].min(0) + tip[:, 1:].max(0)) / 2
        mounts.append({'side': side, 'position': (source_to_native(yaw_pivot, ident) * scale).tolist(),
            'quaternion': [quaternion.x, quaternion.y, quaternion.z, quaternion.w],
            'gun_relative_location': (((pitch_pivot - yaw_pivot) @ basis) * scale).tolist(),
            'muzzle_local': (muzzle * scale).tolist(), 'gun_source_sections': gun_sections,
            'swivel_source_sections': swivel_sections})
    bpy.ops.object.select_all(action='DESELECT')
    (output / 'weapon-rig.json').write_text(json.dumps({'cannon_mounts': mounts,
        'omitted_hull_sections': sorted(omitted), 'scale': scale,
        'requires_gameplay_validation': True}, indent=2) + '\n')
    return omitted
