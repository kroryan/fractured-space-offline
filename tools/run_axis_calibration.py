"""Import an asymmetric fixture without changing the game or fleet meshes."""
import json
from pathlib import Path
import subprocess
import os

root = Path(__file__).resolve().parents[1]
folder = root / 'obj/expanse-authoring/axis-calibration'
folder.mkdir(exist_ok=True)
fbx = folder / 'AxisCalibration.fbx'
subprocess.run([str(root / 'obj/tooling/blender-4.2.23-windows-x64/blender.exe'), '-b', '-t', '2',
                '--python-exit-code', '1', '--python', str(root / 'tools/make_axis_calibration.py'), '--', str(fbx)], check=True)
settings = {'ImportGroups': [{'GroupName': 'AxisCalibration', 'Filenames': [str(fbx)],
    'DestinationPath': '/Game/AuthoringCalibration', 'FactoryName': 'FbxFactory', 'bReplaceExisting': True,
    'ImportSettings': {'MeshTypeToImport': 'FBXIT_StaticMesh', 'bImportMaterials': False,
        'bImportTextures': False, 'StaticMeshImportData': {'bCombineMeshes': True,
            'bForceFrontXAxis': True, 'ImportUniformScale': 1, 'bAutoGenerateCollision': True,
            'StaticMeshLODGroup': 'None', 'bGenerateLightmapUVs': False}}}]}
config = folder / 'settings.json'
config.write_text(json.dumps(settings, indent=2))
environment = dict(os.environ, OPENSSL_ia32cap=':~0x20000000')
with (folder / 'console.log').open('w') as output:
    subprocess.run([r'C:\Program Files\Epic Games\UE_4.19\Engine\Binaries\Win64\UE4Editor-Cmd.exe',
        str(root / 'obj/expanse-authoring/UnrealProject/spacegame.uproject'), '-run=ImportAssets',
        '-importsettings=' + str(config), '-dest=/Game/AuthoringCalibration', '-nosourcecontrol',
        '-nullrhi', '-unattended', '-nop4', '-nosplash', '-abslog=' + str(folder / 'import.log')],
        env=environment, stdout=output, stderr=subprocess.STDOUT, check=True)
print('Imported asymmetric axis calibration fixture.')
