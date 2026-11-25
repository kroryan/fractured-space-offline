import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'linux'))
from proton_support import case_path, launch_command


class BootstrapperUpdateTests(unittest.TestCase):
    def test_published_payload_matches_both_installers(self):
        lock = json.loads((ROOT / 'tools/bootstrapper-lock.json').read_text(encoding='utf-8'))
        cs = (ROOT / 'src/Installer/Installer.cs').read_text(encoding='utf-8')
        py = (ROOT / 'linux/fso_linux.py').read_text(encoding='utf-8')
        for entry in lock['files']:
            self.assertEqual(hashlib.sha256((ROOT / 'patch' / entry['file']).read_bytes()).hexdigest(), entry['sha256'])
            self.assertIn(entry['sha256'], cs)
            self.assertIn(entry['sha256'], py)
        for name in lock['retired_overlays']:
            self.assertFalse((ROOT / 'patch' / name).exists())
            self.assertNotRegex(cs, r'new PatchFile\("' + re.escape(name))

    def test_native_executable_patch_bytes(self):
        data = (ROOT / 'patch/Fractured Space.exe').read_bytes()
        # Published null-lobby guard, drafting refresh, and dead missile filters.
        for offset, value in [(0x207600F, 'e9bcf5f8fd9090'), (0x3B3600, 'e94b23ccff')]:
            expected = bytes.fromhex(value)
            self.assertEqual(data[offset:offset + len(expected)], expected)

    def test_entitlement_routes_and_personal_result_hook(self):
        records = json.loads((ROOT / 'server/responses.json').read_text(encoding='utf-8'))
        licenses = [json.loads(e['response']['content']) for e in records if '/licenses?' in e['request']['url']]
        self.assertTrue(licenses)
        self.assertTrue(all(len(e['licenses']) == 1237 for e in licenses))
        bundle = next(e for e in records if e['request']['url'].endswith('/licenses/bundle/check'))
        self.assertEqual(len(json.loads(bundle['response']['content'])['licenses']), 697)
        self.assertIn('fso-results.json', (ROOT / 'patch/results-script.js').read_text(encoding='utf-8'))

    def test_runtime_container_flatpak_and_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            proton = root / 'Proton/proton'
            proton.parent.mkdir()
            proton.write_text('fixture')
            (proton.parent / 'toolmanifest.vdf').write_text('"require_tool_appid" "1628350"')
            lib = root / 'steamapps'
            entry = lib / 'common/SteamLinuxRuntime_sniper/_v2-entry-point'
            entry.parent.mkdir(parents=True)
            entry.write_text('fixture')
            home = root / 'home'
            steamclient = home / '.var/app/com.valvesoftware.Steam/.steam/sdk64/steamclient.so'
            steamclient.parent.mkdir(parents=True)
            steamclient.write_bytes(b'fixture')
            command, env = launch_command(str(proton), [str(lib)], '/game', ['-discord=offline'],
                {'HOME': str(home), 'APPIMAGE': '/app', 'LD_PRELOAD': 'bad', 'FSO_PLAYER_ID': 'player'})
            self.assertEqual(command[:3], [str(entry), '--verb=waitforexitandrun', '--'])
            self.assertIn('waitforexitandrun', command)
            self.assertNotIn('LD_PRELOAD', env)
            self.assertEqual(env['FSO_PLAYER_ID'], 'player')
            self.assertEqual(env['HOME'], str(home / '.var/app/com.valvesoftware.Steam'))
            entry.unlink()
            with self.assertRaisesRegex(RuntimeError, '1628350'):
                launch_command(str(proton), [str(lib)], '/game', [], {})
            command, _ = launch_command(str(proton), [str(lib)], '/game', [], {}, use_runtime=False)
            self.assertIn('waitforexitandrun', command)

    def test_case_path_does_not_create_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / 'Space/SpaceGame/Binaries/Win64'
            folder.mkdir(parents=True)
            self.assertEqual(os.path.normcase(case_path(str(Path(temp) / 'space/spacegame/binaries/win64'))), os.path.normcase(str(folder)))
            self.assertIsNone(case_path(str(Path(temp) / 'missing')))
            self.assertFalse((Path(temp) / 'missing').exists())

    def test_upgrade_retires_overlays_and_preserves_restore_baseline(self):
        import fso_linux as launcher
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            game, payload = folder / 'game', folder / 'payload'
            pakdir = game / 'spacegame/Content/Paks'
            pakdir.mkdir(parents=True)
            payload.mkdir()
            target = pakdir / 'base.pak'
            target.write_bytes(b'original')
            (payload / 'base.pak').write_bytes(b'first-update')
            (pakdir / 'Makichika_MapJamming_P.pak').write_bytes(b'old-overlay')
            (pakdir / 'FSO_Expanse_Experimental_P.pak').write_bytes(b'secondary-fleet')
            with mock.patch.multiple(launcher, DATA_DIR=str(payload), PATCH_DIR=str(payload),
                    STATE_DIR=str(folder / 'state'), log=lambda message: None):
                for value in (b'first-update', b'second-update'):
                    (payload / 'base.pak').write_bytes(value)
                    with mock.patch.object(launcher, 'PATCH', [('base.pak', 'spacegame/Content/Paks/base.pak', hashlib.sha256(value).hexdigest())]):
                        launcher.patch_game(str(game))
                self.assertEqual(target.read_bytes(), b'second-update')
                self.assertEqual((game / launcher.BACKUP_DIR / 'spacegame/Content/Paks/base.pak').read_bytes(), b'original')
                self.assertFalse((pakdir / 'FSO_Expanse_Experimental_P.pak').exists())
                self.assertFalse((pakdir / 'Makichika_MapJamming_P.pak').exists())
                self.assertEqual(len(list((folder / 'state/disabled-paks').iterdir())), 2)


if __name__ == '__main__':
    unittest.main()
