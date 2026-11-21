"""Verify built AppImage framing and its staged mandatory fleet payload."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
IMAGE = ROOT / 'dist/FracturedSpaceOffline-ExpanseTest-x86_64.AppImage'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').digest()


@unittest.skipUnless(IMAGE.exists(), 'Build the local fleet AppImage first.')
class AppImageFleetTests(unittest.TestCase):
    def test_runtime_and_squashfs_payload(self):
        runtime = ROOT / 'linux/runtime-x86_64'
        squash = ROOT / 'obj/app.squashfs'
        with IMAGE.open('rb') as stream:
            self.assertEqual(stream.read(runtime.stat().st_size), runtime.read_bytes())
            self.assertEqual(stream.read(4), b'hsqs')
            stream.seek(runtime.stat().st_size)
            self.assertEqual(hashlib.file_digest(stream, 'sha256').digest(), digest(squash))
        share = ROOT / 'obj/AppDir/usr/share/fractured-space-offline'
        manifest = json.loads((share / 'fleet-manifest.json').read_text())
        self.assertEqual(len(manifest), 44)
        for entry in manifest:
            self.assertEqual(digest(share / 'patch' / entry['src']).hex(), entry['sha256'])
        self.assertEqual(digest(share / 'responses.json'), digest(ROOT / 'obj/expanse-authoring/candidate-responses.json'))


if __name__ == '__main__':
    unittest.main()
