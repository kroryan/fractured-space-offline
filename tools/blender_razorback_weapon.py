"""Author the requested light-cannon retrofit on Razorback's opaque hull."""
import json
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix
from blender_rocinante_pdc import make_piece, export_piece
from expanse_axes import source_to_blender, source_to_native, blender_to_native


def prepare(metadata, output, materials):
    from blender_expanse import create_material, material_definitions
    roci = output.parent / '2211361535'
    donor = json.loads((roci / 'prepared.json').read_text())
    archive = np.load(roci / donor['geometry'][0]['prepared_geometry'])
    material_name = donor['materials'][2]
    material = create_material(roci / 'source', material_name,
                               material_definitions(roci / 'source')[material_name], False)
    donor_pivot = archive['1_positions'] * donor['unit_metres']
    donor_pivot = (donor_pivot.min(0) + donor_pivot.max(0)) / 2
    forward, up = np.array((0, 0, -1)), np.array((0, -1, 0))
    basis = np.column_stack((forward, np.cross(forward, up), up))
    # A single 0.9 m-class defensive cannon, rather than a capital-ship battery.
    factor = 0.3
    pieces = []
    for suffix, sections in [('Gun', [2, 3]), ('Swivel', [0, 1])]:
        name = 'Cannon_Razorback_' + suffix
        obj = make_piece(name, sections, archive, donor['unit_metres'], basis, donor_pivot, material)
        for vertex in obj.data.vertices:
            vertex.co *= factor
        barrel = (archive['3_positions'] * donor['unit_metres'] - donor_pivot) @ basis * factor
        muzzle = barrel.mean(0)
        muzzle[0] = barrel[:, 0].max()
        export_piece(obj, output / (name + '.fbx'), muzzle if suffix == 'Gun' else None)
        pieces.append(obj)
    # An original mounting collar closes the gap between the source servo and
    # the new hull. Its bottom is the exact contact plane of the surface mount.
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.26, depth=0.12,
                                        location=(0, 0, -0.52))
    base = bpy.context.object
    base.name = 'Cannon_Razorback_Base'
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    base.data.materials.append(materials[0])
    export_piece(base, output / (base.name + '.fbx'))
    pieces.append(base)

    hull = np.load(output / metadata['geometry'][0]['prepared_geometry'])
    points = hull['5_positions'] * metadata['unit_metres']
    triangles = hull['5_triangles']
    # Intersect a downward ray against the opaque painted-hull section, not the
    # cockpit or an arbitrary bounding-box coordinate. Store the source face.
    vertices = points[triangles]
    origin, direction = np.array((0.0, 10.0, 6.0)), np.array((0.0, -1.0, 0.0))
    edge1, edge2 = vertices[:, 1] - vertices[:, 0], vertices[:, 2] - vertices[:, 0]
    cross = np.cross(np.broadcast_to(direction, edge2.shape), edge2)
    det = np.einsum('ij,ij->i', edge1, cross)
    valid = np.abs(det) > 1e-8
    inverse = np.zeros(len(det)); inverse[valid] = 1 / det[valid]
    offset = origin - vertices[:, 0]
    u = np.einsum('ij,ij->i', offset, cross) * inverse
    q = np.cross(offset, edge1)
    v = q @ direction * inverse
    distance = np.einsum('ij,ij->i', edge2, q) * inverse
    valid &= (u >= 0) & (v >= 0) & (u + v <= 1) & (distance > 0)
    if not valid.any():
        raise ValueError('No opaque Razorback hull surface at the reviewed retrofit location')
    face = int(np.flatnonzero(valid)[np.argmin(distance[valid])])
    contact = origin + direction * distance[face]
    normal = np.cross(edge1[face], edge2[face])
    normal /= np.linalg.norm(normal)
    if normal[1] < 0:
        normal *= -1
    heading = np.array((0, 0, 1)) - normal * normal[2]
    heading /= np.linalg.norm(heading)
    rotation_source = np.column_stack((heading, np.cross(heading, normal), normal))
    rotation = source_to_native(rotation_source.T, metadata['workshop_id']).T
    quaternion = Matrix(rotation.tolist()).to_quaternion()
    pivot = contact + normal * 0.58
    conversion = np.array(((0, -1, 0), (-1, 0, 0), (0, 0, 1)))
    transform = Matrix.Translation(source_to_blender(pivot, metadata['workshop_id']).tolist()) @ Matrix(
        (conversion @ rotation @ conversion).tolist()).to_4x4()
    for template in pieces:
        instance = bpy.data.objects.new('Cannon_Retrofit_' + template.name, template.data)
        bpy.context.collection.objects.link(instance)
        instance.matrix_world = transform
    all_points = [hull[str(i) + '_positions'] * metadata['unit_metres'] for i in range(int(hull['mesh_count']))]
    scale = 300 / float(max(np.max([p.max(0) for p in all_points], axis=0) -
                              np.min([p.min(0) for p in all_points], axis=0)))
    (output / 'cannon-rig.json').write_text(json.dumps({
        'position': (source_to_native(pivot, metadata['workshop_id']) * scale).tolist(),
        'quaternion': [quaternion.x, quaternion.y, quaternion.z, quaternion.w],
        'source_contact': contact.tolist(), 'source_surface_normal': normal.tolist(),
        'source_hull_section': 5, 'source_hull_triangle': face, 'source_material': metadata['materials'][2],
        'cannon_count': 1, 'donor_workshop_id': '2211361535', 'donor_scale': factor,
        'original_weapon_geometry_removed': 0, 'reason': 'The original racing hull has no weapon.',
        'requires_gameplay_validation': True}, indent=2) + '\n')
    bpy.ops.object.select_all(action='DESELECT')
