"""Prepare the two original mid-fore torpedo bays in a launch-ready pose.

Placement was reviewed against the source hatches and Ryan Dening's production
turnaround. The small chemical-thruster recesses at the bow are not launchers.
The original hatch leaves are reused, not covered by added launcher models.
"""
import json
import math
import bpy
import numpy as np
from mathutils import Matrix
from expanse_axes import source_to_native, source_to_blender


def prepare(metadata, output):
    archive = np.load(output / metadata['geometry'][0]['prepared_geometry'])
    unit, ident = metadata['unit_metres'], metadata['workshop_id']
    raw = [archive[str(i) + '_positions'].astype(np.float64) * unit for i in range(int(archive['mesh_count']))]
    scale = 600 / float(max(np.max([p.max(0) for p in raw], axis=0) - np.min([p.min(0) for p in raw], axis=0)))
    overrides, ports = {}, []
    axis = np.array((1.0, 0.0, 0.0))
    for label, sections in [('Ventral', (60, 61)), ('Dorsal', (62, 66))]:
        centers = [(raw[i].min(0) + raw[i].max(0)) / 2 for i in sections]
        tangent = centers[1] - centers[0]
        tangent /= np.linalg.norm(tangent)
        normal = np.cross(axis, tangent)
        if normal[2] > 0:
            normal *= -1
        normal /= np.linalg.norm(normal)
        combined = np.concatenate([raw[i] for i in sections])
        contact = (combined.min(0) + combined.max(0)) / 2
        width = float(np.ptp(combined[:, 0])) * 0.82
        height = float(np.ptp(combined @ tangent)) * 0.82
        for leaf, section in enumerate(sections):
            points = raw[section]
            local = points @ tangent
            edge = local.min() if leaf == 0 else local.max()
            hinge = centers[leaf] + tangent * (edge - centers[leaf] @ tangent)
            sign = np.sign(np.dot(np.cross(axis, tangent), normal)) * (1 if leaf == 0 else -1)
            rotation = np.array(Matrix.Rotation(float(sign * math.pi / 2), 3, 'X'))
            overrides[section] = {
                'positions': (((points - hinge) @ rotation.T + hinge) / unit).astype(np.float32),
                'normals': (archive[str(section) + '_normals'] @ rotation.T).astype(np.float32)}
        # StaticTurret's local +X points out of the source bay; guidance can
        # then steer the native torpedo toward its selected target.
        up = np.array((0.0, 1.0, 0.0))
        up -= normal * np.dot(normal, up)
        up /= np.linalg.norm(up)
        basis = np.column_stack((normal, np.cross(normal, up), up))
        quaternion = Matrix(source_to_native(basis.T, ident).T.tolist()).to_quaternion()
        ports.append({'name': label, 'source_sections': list(sections), 'source_contact': contact.tolist(),
            'source_normal': normal.tolist(), 'opening_width': width, 'opening_height': height,
            'source_tangent': np.cross(normal, axis).tolist(),
            'position': (source_to_native(contact + normal * 0.04, ident) * scale).tolist(),
            'quaternion': [quaternion.x, quaternion.y, quaternion.z, quaternion.w]})
    rig = {'ports': ports, 'scale': scale, 'door_pose': 'static launch-ready',
           'reference': 'https://deningart.artstation.com/projects/zQwR6',
           'requires_gameplay_validation': True}
    (output / 'torpedo-rig.json').write_text(json.dumps(rig, indent=2) + '\n')
    return overrides, rig


def open_bays(hull, rig, ident):
    before = len(hull.data.polygons)
    sleeves = []
    material = bpy.data.materials.new('FSO_Rocinante_TorpedoBay_Interior')
    material.use_nodes = True
    shader = material.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (0.025, 0.03, 0.035, 1)
    shader.inputs['Metallic'].default_value = 0.7
    shader.inputs['Roughness'].default_value = 0.5
    for port in rig['ports']:
        center, normal = np.array(port['source_contact']), np.array(port['source_normal'])
        tangent = np.array(port['source_tangent'])
        basis = np.column_stack(((1, 0, 0), tangent, normal))
        rotation = Matrix(source_to_blender(basis.T, ident).T.tolist()).to_4x4()
        translation = Matrix.Translation(source_to_blender(center - normal * 0.25, ident).tolist())
        bpy.ops.mesh.primitive_cube_add(size=1)
        cutter = bpy.context.object
        cutter.name = 'AuthoringOnly_TorpedoBayCut_' + port['name']
        cutter.matrix_world = translation @ rotation @ Matrix.Diagonal(
            (port['opening_width'], port['opening_height'], 1.0, 1.0))
        bpy.context.view_layer.objects.active = hull
        modifier = hull.modifiers.new('OpenOriginalTorpedoBay_' + port['name'], 'BOOLEAN')
        modifier.operation = 'DIFFERENCE'; modifier.solver = 'EXACT'; modifier.object = cutter
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        bpy.data.objects.remove(cutter, do_unlink=True)
        width, height = port['opening_width'] / 2, port['opening_height'] / 2
        front = np.array([[-width, -height, 0], [width, -height, 0],
                          [width, height, 0], [-width, height, 0]])
        back = front + (0, 0, -1.2)
        points = source_to_blender(np.concatenate((front, back)) @ basis.T + center, ident)
        faces = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7)]
        mesh = bpy.data.meshes.new('TorpedoBaySleeve_' + port['name'])
        mesh.from_pydata(points.tolist(), [], faces); mesh.update()
        mesh.materials.append(material)
        sleeve = bpy.data.objects.new(mesh.name, mesh)
        bpy.context.collection.objects.link(sleeve)
        sleeves.append(sleeve)
    if not before * 0.9 <= len(hull.data.polygons) <= before * 1.15:
        raise ValueError('Torpedo-bay cuts changed unrelated hull geometry')
    bpy.ops.object.select_all(action='DESELECT')
    hull.select_set(True)
    for sleeve in sleeves:
        sleeve.select_set(True)
    bpy.context.view_layer.objects.active = hull
    bpy.ops.object.join()
