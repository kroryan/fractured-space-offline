"""Repair the normal offline patch after a restore/uninstall, preserving profiles.

Run a normal build first. This tool checks every source hash, records replaced
files under obj/repair-backups and retains the original game's restore backups.
It does not install the Expanse fleet or change account/profile data.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--game', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    game = args.game.resolve()
    if not (game / 'spacegame/Binaries/Win64/Fractured Space.exe').is_file():
        raise SystemExit('Game executable not found.')
    source = (ROOT / 'src/Installer/Installer.cs').read_text(encoding='utf-8-sig')
    records = re.findall(r'new PatchFile\("([^"]+)", @"([^"]+)", "([a-f0-9]+)"', source)
    planned = []
    for name, relative, expected in records:
        payload = ROOT / 'patch' / name
        target = game / Path(relative.replace('\\', '/'))
        if not target.resolve().is_relative_to(game):
            raise ValueError('Invalid game destination')
        if digest(payload) != expected:
            raise ValueError('Source patch hash mismatch: ' + name)
        if not target.exists() or digest(target) != expected:
            planned.append((payload, target, expected))
    wrapper = ROOT / 'obj/spserver-wrapper.exe'
    if not wrapper.is_file():
        raise SystemExit('Build the normal installer before repair: missing server wrapper.')
    server = game / 'spacegame/Binaries/Win64/spserver.exe'
    original = server.with_name('spserver_original.exe')
    if not original.is_file():
        raise SystemExit('Original dedicated server backup is missing; use the normal installer.')
    if digest(server) != digest(wrapper):
        planned.append((wrapper, server, digest(wrapper)))
    print('Normal offline files requiring repair:', len(planned))
    if not args.apply:
        return
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    recovery = ROOT / 'obj/repair-backups' / stamp
    original_backup = game / 'fractured-offline-backup'
    report = []
    for payload, target, expected in planned:
        relative = target.relative_to(game)
        saved = recovery / relative
        if target.exists():
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
        baseline = original_backup / relative
        absent = baseline.with_name(baseline.name + '.fso-absent')
        if not baseline.exists() and not absent.exists():
            baseline.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                shutil.copy2(target, baseline)
            else:
                absent.write_bytes(b'')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(payload, target)
        if digest(target) != expected:
            raise ValueError('Repaired file failed verification: ' + str(relative))
        report.append({'file': relative.as_posix(), 'sha256': expected})
    recovery.mkdir(parents=True, exist_ok=True)
    (recovery / 'repair.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Repaired and verified', len(report), 'normal offline files.')
    print('Recovery copy:', recovery)


if __name__ == '__main__':
    main()
