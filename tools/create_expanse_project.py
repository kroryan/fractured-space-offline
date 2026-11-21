"""Generate an isolated UE4.19 authoring project and explicit automated-import settings.

python tools/create_expanse_project.py --ship 2211361535
Requires prepared FBX files. Does not modify the installed game or start Unreal.
"""
import argparse
import json
from pathlib import Path
import re
import numpy as np
from audit_expanse import PACKS

ROOT = Path(__file__).resolve().parents[1]
GAMEPLAY_ENVELOPE = {'2211361535': 600, '2224316655': 300, '2368610280': 300,
                     '2375119898': 1500, '2375181309': 350, '2687045417': 1200,
                     '2687094193': 700}

def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--ship', choices=list(PACKS), action='append')
    args = parser.parse_args()
    project = ROOT / 'obj/expanse-authoring/UnrealProject'
    (project / 'Config').mkdir(parents=True, exist_ok=True)
    (project / 'Content/Expanse').mkdir(parents=True, exist_ok=True)
    description = {'FileVersion': 3, 'EngineAssociation': '4.19', 'Category': 'ModAuthoring',
                   'Description': 'Local asset-authoring project for Fractured Space Offline',
                   'Plugins': [{'Name': 'PythonScriptPlugin', 'Enabled': True}]}
    (project / 'spacegame.uproject').write_text(json.dumps(description, indent=2), encoding='utf-8')
    # Stock hangars request precomputed volumetric-lightmap permutations even
    # for movable ships. Disabling static lighting strips those shader variants
    # and the shipping client cannot compile them when a new ship is selected.
    (project / 'Config/DefaultEngine.ini').write_text('[Core.System]\n+Paths=../../../Engine/Content\n\n[/Script/Engine.RendererSettings]\nr.AllowStaticLighting=True\nr.SupportLowQualityLightmaps=True\n', encoding='utf-8')
    (project / 'Config/DefaultGame.ini').write_text('[/Script/UnrealEd.ProjectPackagingSettings]\nbCookAll=False\nbUsePakFile=True\n+DirectoriesToAlwaysCook=(Path="/Game/Expanse")\n', encoding='utf-8')
    groups = []
    for ident in args.ship or PACKS:
        folder = ROOT / 'obj/expanse-authoring' / ident
        metadata = json.loads((folder / 'prepared.json').read_text(encoding='utf-8'))
        lower, upper = None, None
        for item in metadata['geometry']:
            with np.load(folder / item['prepared_geometry']) as geometry:
                for section in range(int(geometry['mesh_count'])):
                    points = geometry[str(section) + '_positions'] * metadata['unit_metres']
                    lower = points.min(0) if lower is None else np.minimum(lower, points.min(0))
                    upper = points.max(0) if upper is None else np.maximum(upper, points.max(0))
        import_scale = GAMEPLAY_ENVELOPE[ident] / float(max(upper - lower))
        name = re.sub(r'[^A-Za-z0-9_]', '_', metadata['display_name'])
        fbx = folder / (name + '.fbx')
        if not fbx.is_file():
            raise SystemExit('Export the review FBX first: ' + str(fbx))
        groups.append({'GroupName': name, 'Filenames': [str(fbx)],
                       'DestinationPath': '/Game/Expanse/' + name, 'FactoryName': 'FbxFactory',
                       'bReplaceExisting': True, 'bSkipReadOnly': True,
                       'ImportSettings': {'MeshTypeToImport': 'FBXIT_StaticMesh',
                                          'bImportAsSkeletal': False, 'bImportAnimations': False,
                                          'bImportMaterials': True, 'bImportTextures': True,
                                          'StaticMeshImportData': {'bCombineMeshes': True,
                                                                   'bForceFrontXAxis': True,
                                                                   'ImportUniformScale': import_scale,
                                                                   'bAutoGenerateCollision': True,
                                                                   'bRemoveDegenerates': True,
                                                                   'bGenerateLightmapUVs': False,
                                                                   # LODs are authored before import. UE4.19's
                                                                   # automatic LargeProp reduction can allocate
                                                                   # multiple gigabytes for a capital-ship hull.
                                                                   'StaticMeshLODGroup': 'None',
                                                                   'NormalImportMethod': 'FBXNIM_ComputeNormals'}}})
        hull_group = groups[-1]
        armour = folder / ('SM_ARM_EXP_' + name + '.fbx')
        if armour.is_file():
            import copy
            armour_group = copy.deepcopy(groups[-1])
            armour_group['GroupName'] = 'SM_ARM_EXP_' + name
            armour_group['Filenames'] = [str(armour)]
            armour_group['ImportSettings']['bImportTextures'] = False
            groups.append(armour_group)
        if ident in ('2211361535', '2375119898', '2224316655', '2687045417', '2687094193', '2375181309'):
            import copy
            patterns = {'2211361535': ['PDC_Rocinante_*.fbx'], '2375119898': ['Railgun_Donnager_*.fbx'],
                        '2224316655': ['Cannon_Razorback_*.fbx'],
                        '2687045417': ['PDC_Mayotte_*.fbx', 'Railgun_Mayotte_*.fbx'],
                        '2687094193': ['Cannon_Avalanche_*.fbx'], '2375181309': ['Cannon_Chariot_*.fbx']}[ident]
            for part in sorted(part for pattern in patterns for part in folder.glob(pattern)):
                part_group = copy.deepcopy(hull_group)
                part_group['GroupName'] = part.stem
                part_group['Filenames'] = [str(part)]
                part_group['DestinationPath'] = '/Game/Expanse/' + name
                part_group['ImportSettings']['StaticMeshImportData']['bAutoGenerateCollision'] = False
                groups.append(part_group)
    settings = project / 'import-settings.json'
    settings.write_text(json.dumps({'ImportGroups': groups}, indent=2), encoding='utf-8')
    print('Project:', project / 'spacegame.uproject')
    print('Import settings:', settings)
    print('These imports are geometry/material preparation, not completed ship registration.')

if __name__ == '__main__':
    main()
