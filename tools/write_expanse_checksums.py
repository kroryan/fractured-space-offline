"""Write checksums for the current local fleet test binaries after a build."""
import hashlib
from pathlib import Path

root = Path(__file__).resolve().parents[1]
dist = root / 'dist'
lines = []
for name in ('FracturedSpaceOfflineSetup-ExpanseTest.exe', 'FracturedSpaceOffline-ExpanseTest-x86_64.AppImage'):
    digest = hashlib.sha256()
    with (dist / name).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    lines.append(digest.hexdigest() + '  ' + name)
(dist / 'EXPANSE-SHA256SUMS.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('Updated local fleet test artifact checksums.')
