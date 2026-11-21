"""Separate the two reviewed source railguns without adding duplicate geometry.

The source joins every material into one section. Connected-component IDs are
therefore required: cutting arbitrary faces would leave fractured gun parts.
The two original bearings remain at their original positions on the hull.
"""
import json
import bpy
import numpy as np
from blender_rocinante_pdc import make_piece, export_piece
from expanse_axes import source_to_blender, source_to_native


def prepare(metadata, output, materials):
    review = json.loads((output / 'component-review.json').read_text())
    archive = np.load(output / metadata['geometry'][0]['prepared_geometry'])
    labels = np.load(output / 'components-0.npz')['face_component']
    unit = metadata['unit_metres']
    removed = np.zeros(len(labels), dtype=bool)
    bounds = [archive[str(i) + '_positions'] * unit for i in range(int(archive['mesh_count']))]
    scale = 1500 / float(max(np.max([p.max(0) for p in bounds], axis=0) -
                               np.min([p.min(0) for p in bounds], axis=0)))
    mounts = []
    # Native X forward / Z up equals source Z forward / Y up for this hull.
    basis = np.array(((0, -1, 0), (0, 0, 1), (1, 0, 0)))
    for side, sign in [('Port', -1), ('Starboard', 1)]:
        selected = [item for item in review if item['section'] == 0
                    and min(sign * item['lower'][0], sign * item['upper'][0]) > 42
                    and max(sign * item['lower'][0], sign * item['upper'][0]) < 54
                    and item['lower'][1] > -9 and item['upper'][1] < 9
                    and item['lower'][2] > 60 and item['upper'][2] < 153]
        expected = 63447 if sign == -1 else 63448
        if len(selected) != 437 or sum(item['triangles'] for item in selected) != expected:
            raise ValueError('Donnager source railgun component selection changed; review it again.')
        ring = next(item for item in selected if item['triangles'] == 12536)
        pivot = np.array(ring['center'])
        swivel_ids = [item['component'] for item in selected
                      if abs(item['center'][2] - pivot[2]) < 0.02]
        mask = np.isin(labels, [item['component'] for item in selected])
        if np.any(removed & mask):
            raise ValueError('Overlapping railgun geometry selections')
        removed |= mask
        muzzle = None
        for suffix, part_mask in [('Swivel', mask & np.isin(labels, swivel_ids)),
                                  ('Gun', mask & ~np.isin(labels, swivel_ids))]:
            selected_faces = archive['0_triangles'][part_mask]
            proxy = {key: archive[key] for key in ['0_positions', '0_normals', '0_uv']}
            proxy['0_triangles'] = selected_faces
            name = 'Railgun_Donnager_' + side + '_' + suffix
            obj = make_piece(name, [0], proxy, unit, basis, pivot,
                             materials[int(archive['0_material'])])
            if suffix == 'Gun':
                points = archive['0_positions'][np.unique(selected_faces)] * unit
                # The two rails end at the same forward plane; the projectile
                # exits the central bore between them, not at one rail's edge.
                muzzle = np.array((points[:, 2].max() - pivot[2], 0.0, 0.0))
            export_piece(obj, output / (name + '.fbx'), muzzle if suffix == 'Gun' else None)
            instance = bpy.data.objects.new('Railgun_Mount_' + side + '_' + suffix, obj.data)
            bpy.context.collection.objects.link(instance)
            instance.location = source_to_blender(pivot, metadata['workshop_id'])
        mounts.append({'side': side, 'position': (source_to_native(pivot, metadata['workshop_id']) * scale).tolist(),
                       'quaternion': [0, 0, 0, 1], 'muzzle_local': (muzzle * scale).tolist(),
                       'source_pivot': pivot.tolist(), 'components': [item['component'] for item in selected],
                       'source_triangles': expected, 'swivel_components': swivel_ids})
    bpy.ops.object.select_all(action='DESELECT')
    (output / 'railgun-rig.json').write_text(json.dumps({'mounts': mounts, 'scale': scale,
        'removed_source_triangles': int(removed.sum()), 'requires_gameplay_validation': True}, indent=2) + '\n')
    return {0: removed}
