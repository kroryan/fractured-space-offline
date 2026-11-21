"""Read local UE4 PAK v4/v5 content for mod authoring, validating stored SHA-1 hashes.

Use --key-file with a local CryptoKeys-style JSON file; keys and extracted stock
content belong in ignored obj/, not in the repository or end-user installer.
Requires pycryptodome only when an encrypted entry is encountered.
"""
import argparse
import base64
import fnmatch
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import zlib


class Pak:
    def __init__(self, path, key=None):
        self.data = Path(path).read_bytes()
        self.key = key
        if len(self.data) < 45:
            raise ValueError('Truncated PAK')
        magic, version, offset, size, expected = struct.unpack_from('<IIqq20s', self.data, len(self.data) - 44)
        if magic != 0x5A6F12E1 or version not in (4, 5):
            raise ValueError('Unsupported PAK version')
        if self.data[-45] != 0:
            raise ValueError('Encrypted indexes are not supported by this authoring reader')
        if offset < 0 or size < 0 or offset + size > len(self.data) - 45:
            raise ValueError('Invalid PAK index bounds')
        index = self.data[offset:offset + size]
        if hashlib.sha1(index).digest() != expected:
            raise ValueError('PAK index hash mismatch')
        stream = io.BytesIO(index)
        self.version = version
        self.mount = self.string(stream)
        count = self.unpack(stream, '<i')[0]
        if not 0 <= count <= 1000000:
            raise ValueError('Invalid entry count')
        self.entries = {}
        for _ in range(count):
            name = self.string(stream)
            begin = stream.tell()
            entry_offset, packed, unpacked, method = self.unpack(stream, '<qqqI')
            digest = stream.read(20)
            blocks = []
            if method:
                block_count = self.unpack(stream, '<i')[0]
                if not 0 < block_count <= 1000000:
                    raise ValueError('Invalid compressed block count')
                blocks = [self.unpack(stream, '<qq') for _ in range(block_count)]
            encrypted, block_size = self.unpack(stream, '<BI')
            if min(entry_offset, packed, unpacked) < 0 or method not in (0, 1):
                raise ValueError('Invalid entry bounds or unsupported compression')
            self.entries[name] = {'offset': entry_offset, 'packed': packed, 'size': unpacked,
                                  'method': method, 'hash': digest, 'blocks': blocks,
                                  'encrypted': bool(encrypted), 'header': stream.tell() - begin}
        if stream.tell() != len(index):
            raise ValueError('Unexpected trailing PAK index data')

    @staticmethod
    def unpack(stream, fmt):
        data = stream.read(struct.calcsize(fmt))
        if len(data) != struct.calcsize(fmt):
            raise ValueError('Truncated PAK entry')
        return struct.unpack(fmt, data)

    @classmethod
    def string(cls, stream):
        count = cls.unpack(stream, '<i')[0]
        if abs(count) > 4096:
            raise ValueError('Invalid PAK string length')
        size = count if count >= 0 else -count * 2
        data = stream.read(size)
        if len(data) != size:
            raise ValueError('Truncated PAK string')
        return data.decode('utf-8' if count >= 0 else 'utf-16-le').rstrip('\0')

    def read(self, name):
        entry = self.entries[name]
        cipher = None
        if entry['encrypted']:
            if self.key is None or len(self.key) != 32:
                raise ValueError('A valid local content key is required for this entry')
            from Crypto.Cipher import AES
            cipher = AES.new(self.key, AES.MODE_ECB)
        blocks = entry['blocks'] if entry['method'] else [(entry['offset'] + entry['header'], entry['offset'] + entry['header'] + entry['packed'])]
        stored, decoded = [], []
        for start, end in blocks:
            if entry['method'] and self.version >= 5:
                start, end = start + entry['offset'], end + entry['offset']
            size = end - start
            padded = ((size + 15) // 16 * 16) if cipher else size
            if start < 0 or size < 0 or start + padded > len(self.data):
                raise ValueError('Invalid PAK data block bounds')
            raw = self.data[start:start + padded]
            stored.append(raw)
            plain = cipher.decrypt(raw)[:size] if cipher else raw
            decoded.append(zlib.decompress(plain) if entry['method'] else plain)
        if hashlib.sha1(b''.join(stored)).digest() != entry['hash']:
            raise ValueError('Stored entry hash mismatch: ' + name)
        output = b''.join(decoded)
        if len(output) != entry['size']:
            raise ValueError('Decoded entry size mismatch: ' + name)
        return output


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('pak', type=Path)
    parser.add_argument('--key-file', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--filter', default='*')
    args = parser.parse_args()
    local_dependencies = Path(__file__).resolve().parents[1] / 'obj/tooling/python'
    sys.path.insert(0, str(local_dependencies))
    key = None
    if args.key_file:
        key = base64.b64decode(json.loads(args.key_file.read_text())['EncryptionKey']['Key'])
    pak = Pak(args.pak, key)
    root = args.out.resolve()
    root.mkdir(parents=True, exist_ok=True)
    count = 0
    for name in pak.entries:
        if not fnmatch.fnmatchcase(name, args.filter):
            continue
        dest = (root / name).resolve()
        if not dest.is_relative_to(root):
            raise ValueError('Unsafe PAK extraction path')
        data = pak.read(name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        count += 1
    print('Validated and extracted', count, 'entries from local PAK. Mount:', pak.mount)

if __name__ == '__main__':
    main()
