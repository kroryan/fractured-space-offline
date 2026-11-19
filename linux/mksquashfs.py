#!/usr/bin/env python3
"""Minimal SquashFS 4.0 writer (zlib/gzip compression, no fragments, no xattrs).

Enough to build an AppImage on any OS (including Windows) without squashfs-tools:
    python mksquashfs.py <source_dir> <output.squashfs> [--exec name ...]

Regular files and directories only. Files listed with --exec (relative paths, or
basenames) get mode 0755; other files 0644; directories 0755. Owner is root (uid/gid 0).
"""
import os
import struct
import sys
import time
import zlib

BLOCK_SIZE = 131072
BLOCK_LOG = 17
META_SIZE = 8192
COMP_GZIP = 1
FLAG_NO_FRAGMENTS = 0x0010
FLAG_NO_XATTRS = 0x0200
NONE64 = 0xFFFFFFFFFFFFFFFF

T_DIR, T_FILE = 1, 2


class MetaWriter:
    """Writes squashfs metadata blocks (8 KiB, each compressed if it helps)."""

    def __init__(self):
        self.out = bytearray()   # finished (compressed) blocks
        self.buf = bytearray()   # current uncompressed block

    def pos(self):
        """(block start relative to table start, offset inside uncompressed block)"""
        return len(self.out), len(self.buf)

    def write(self, data):
        self.buf += data
        while len(self.buf) >= META_SIZE:
            self._flush(self.buf[:META_SIZE])
            self.buf = self.buf[META_SIZE:]

    def _flush(self, block):
        c = zlib.compress(bytes(block), 9)
        if len(c) < len(block):
            self.out += struct.pack("<H", len(c)) + c
        else:
            self.out += struct.pack("<H", len(block) | 0x8000) + block

    def finish(self):
        if self.buf:
            self._flush(self.buf)
            self.buf = bytearray()
        return bytes(self.out)


class Node:
    def __init__(self, path, name, is_dir):
        self.path, self.name, self.is_dir = path, name, is_dir
        self.children = []
        self.ino = 0
        self.ref = None  # (block, offset) in inode table
        self.mode = 0o755 if is_dir else 0o644
        self.size = 0
        self.blocks_start = 0
        self.block_sizes = []


def scan(path, name, exec_names, rel=""):
    n = Node(path, name, os.path.isdir(path))
    if n.is_dir:
        for child in sorted(os.listdir(path), key=lambda s: s.encode("utf-8")):
            crel = (rel + "/" + child) if rel else child
            n.children.append(scan(os.path.join(path, child), child, exec_names, crel))
    else:
        n.size = os.path.getsize(path)
        if rel in exec_names or name in exec_names:
            n.mode = 0o755
    return n


def walk_post(n):
    for c in n.children:
        yield from walk_post(c)
    yield n


def build(src, dst, exec_names=()):
    mtime = int(time.time())
    root = scan(src, "", set(exec_names))
    nodes = list(walk_post(root))
    for i, n in enumerate(nodes, 1):   # post-order: children before parents, root last
        n.ino = i
    inode_count = len(nodes)

    img = bytearray(96)  # superblock placeholder

    # ---- data blocks
    for n in nodes:
        if n.is_dir or n.size == 0:
            continue
        n.blocks_start = len(img)
        with open(n.path, "rb") as fh:
            while True:
                chunk = fh.read(BLOCK_SIZE)
                if not chunk:
                    break
                c = zlib.compress(chunk, 6)
                if len(c) < len(chunk):
                    img += c
                    n.block_sizes.append(len(c))
                else:
                    img += chunk
                    n.block_sizes.append(len(chunk) | (1 << 24))

    # ---- inodes + directories (post-order so children refs are known)
    inodes, dirs = MetaWriter(), MetaWriter()
    parent_of = {}
    for n in nodes:
        for c in n.children:
            parent_of[id(c)] = n

    for n in nodes:
        n.ref = inodes.pos()
        if n.is_dir:
            dstart, doff = dirs.pos()
            listing = bytearray()
            i = 0
            kids = n.children
            while i < len(kids):
                blk = kids[i].ref[0]
                base = kids[i].ino
                group = []
                while (i < len(kids) and len(group) < 256 and kids[i].ref[0] == blk
                       and -32768 <= kids[i].ino - base <= 32767):
                    group.append(kids[i])
                    i += 1
                listing += struct.pack("<III", len(group) - 1, blk, base)
                for k in group:
                    nm = k.name.encode("utf-8")
                    listing += struct.pack("<HhHH", k.ref[1], k.ino - base,
                                           T_DIR if k.is_dir else T_FILE, len(nm) - 1) + nm
            dirs.write(listing)
            nlink = 2 + sum(1 for k in kids if k.is_dir)
            parent = parent_of.get(id(n))
            parent_ino = parent.ino if parent else inode_count + 1
            file_size = len(listing) + 3
            if file_size > 0xFFFF:
                raise SystemExit("directory too large for basic inode: " + n.path)
            inodes.write(struct.pack("<HHHHII", T_DIR, n.mode, 0, 0, mtime, n.ino) +
                         struct.pack("<IIHHI", dstart, nlink, file_size, doff, parent_ino))
        else:
            inodes.write(struct.pack("<HHHHII", T_FILE, n.mode, 0, 0, mtime, n.ino) +
                         struct.pack("<IIII", n.blocks_start if n.size else 0, 0xFFFFFFFF, 0, n.size) +
                         b"".join(struct.pack("<I", b) for b in n.block_sizes))

    inode_table_start = len(img)
    img += inodes.finish()
    dir_table_start = len(img)
    img += dirs.finish()

    # ---- id table: one id (0); table = metadata block + array of pointers to it
    ids = MetaWriter()
    ids.write(struct.pack("<I", 0))
    id_block_pos = len(img)
    img += ids.finish()
    id_table_start = len(img)
    img += struct.pack("<Q", id_block_pos)

    bytes_used = len(img)
    root_ref = (root.ref[0] << 16) | root.ref[1]
    sb = struct.pack("<IIIIIHHHHHHQQQQQQQQ",
                     0x73717368, inode_count, mtime, BLOCK_SIZE, 0,
                     COMP_GZIP, BLOCK_LOG, FLAG_NO_FRAGMENTS | FLAG_NO_XATTRS, 1, 4, 0,
                     root_ref, bytes_used, id_table_start, NONE64,
                     inode_table_start, dir_table_start, NONE64, NONE64)
    assert len(sb) == 96
    img[0:96] = sb
    img += b"\0" * (-len(img) % 4096)  # pad like mksquashfs
    with open(dst, "wb") as fh:
        fh.write(img)
    return inode_count, len(img)


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2:
        raise SystemExit(__doc__)
    ex = []
    if "--exec" in a:
        i = a.index("--exec")
        ex = a[i + 1:]
        a = a[:i]
    count, size = build(a[0], a[1], ex)
    print("squashfs: %d inodes, %d bytes" % (count, size))
