"""Package locally cooked fleet content for isolated runtime testing.

This creates an experimental PAK in obj/. It never updates the installed game,
installer payload, Git remote or releases. Cooking and packaging do not prove
that registration, hardpoints or gameplay work in the native game.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import shutil
from build_expanse_fleet import stable_guid

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--unreal-pak', type=Path, default=Path(
        'C:/Program Files/Epic Games/UE_4.19/Engine/Binaries/Win64/UnrealPak.exe'))
    args = parser.parse_args()
    authoring = ROOT / 'obj/expanse-authoring'
    cooked = authoring / 'UnrealProject/Saved/Cooked/WindowsNoEditor/spacegame/Content/Expanse'
    cloned = authoring / 'patch-content/Content'
    expected = ['Rocinante', 'Razorback', 'MCRN_Donnager', 'MCRN_Avalanche',
                'UNN_Mayotte', 'MCRN_Chariot_Type_Dropship', 'Epstein_s_Yacht']
    for name in expected:
        if not (cooked / name / (name + '.uasset')).is_file():
            raise SystemExit('Missing cooked ship mesh: ' + name)
        if not (cooked / name / ('SM_ARM_EXP_' + name + '.uasset')).is_file():
            raise SystemExit('Missing six-region cooked armour mesh: ' + name)
    subprocess.run([str(ROOT / 'obj/tooling/dotnet/dotnet.exe'),
                    str(ROOT / 'tools/FleetAssetTool/bin/Debug/net10.0/FleetAssetTool.dll'),
                    'check-lighting', str(cooked)], check=True)
    entries = {}
    for path in cooked.rglob('*'):
        if path.is_file():
            entries['Expanse/' + path.relative_to(cooked).as_posix()] = path
    for folder in ['Blueprints', 'Ships', 'Expanse']:
        for path in (cloned / folder).rglob('*'):
            if path.is_file() and path.name != 'expanse-fleet-index.json':
                entries[path.relative_to(cloned).as_posix()] = path
    response = authoring / 'expanse-local-pak-response.txt'
    response.write_text('\n'.join(
        f'"{source}" "../../../spacegame/Content/{target}"'
        for target, source in sorted(entries.items())) + '\n', encoding='utf-8')
    destination = authoring / 'FSO_Expanse_Experimental_P.pak'
    subprocess.run([str(args.unreal_pak), str(destination), '-Create=' + str(response), '-compress'], check=True)
    subprocess.run([str(args.unreal_pak), str(destination), '-Test'], check=True)
    manifest = [{'src': destination.name,
                 'dest': 'spacegame/Content/Paks/' + destination.name,
                 'sha256': hashlib.sha256(destination.read_bytes()).hexdigest()}]
    notices = ROOT / 'mods/expanse/ASSET_NOTICES.txt'
    manifest.append({'src': 'expanse-asset-notices.txt',
                     'dest': 'spacegame/Content/Expanse/ASSET_NOTICES.txt',
                     'sha256': hashlib.sha256(notices.read_bytes()).hexdigest()})
    shutil.copyfile(notices, authoring / 'expanse-asset-notices.txt')
    for spec in json.loads((ROOT / 'mods/expanse/fleet.json').read_text()):
        guid = stable_guid(spec['slug'], 'ship')
        for name in ('main', 'store', 'large', 'bronze', 'silver', 'gold'):
            portrait = authoring / 'portraits' / guid / (name + '.png')
            if not portrait.is_file():
                raise SystemExit('Missing mandatory native selector portrait: ' + str(portrait))
            source_name = 'expanse-' + guid + '-' + name + '.png'
            shutil.copyfile(portrait, authoring / source_name)
            manifest.append({'src': source_name,
                'dest': 'spacegame/Content/UIResources/frontend/images/ships/' + guid + '/' + name + '.png',
                'sha256': hashlib.sha256(portrait.read_bytes()).hexdigest()})
    (authoring / 'fleet-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print('Created experimental local PAK:', destination)
    print('Runtime registration, weapons and installer integration remain separate validation gates.')


if __name__ == '__main__':
    main()
