#!/usr/bin/env python3
"""Builds dist/FracturedSpaceOffline-x86_64.AppImage (works on Windows, Linux or macOS).

    python linux/build_appimage.py

AppImage = AppImage type2 runtime (linux/runtime-x86_64, from AppImage/type2-runtime)
           + a SquashFS image of the AppDir (made by linux/mksquashfs.py).
"""
import os
import shutil
import struct
import sys

LINUX = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(LINUX)
sys.path.insert(0, LINUX)
import mksquashfs  # noqa: E402

OBJ = os.path.join(ROOT, "obj")
APPDIR = os.path.join(OBJ, "AppDir")
DIST = os.path.join(ROOT, "dist")
OUT = os.path.join(DIST, "FracturedSpaceOffline-x86_64.AppImage")
SHARE = "usr/share/fractured-space-offline"


def png_from_ico(ico_path):
    """Return the largest PNG image stored in an .ico file."""
    data = open(ico_path, "rb").read()
    count = struct.unpack_from("<H", data, 4)[0]
    best = None
    for i in range(count):
        w, h, _, _, _, _, size, off = struct.unpack_from("<BBBBHHII", data, 6 + 16 * i)
        w = w or 256
        img = data[off:off + size]
        if img[:8] == b"\x89PNG\r\n\x1a\n" and (best is None or w > best[0]):
            best = (w, img)
    if not best:
        raise SystemExit("no PNG image in " + ico_path)
    return best[1]


def copy_lf(src, dst):
    """Copy a text file forcing LF line endings (scripts must not have CRLF)."""
    with open(src, "rb") as fh:
        data = fh.read().replace(b"\r\n", b"\n")
    with open(dst, "wb") as fh:
        fh.write(data)


def main():
    shutil.rmtree(APPDIR, ignore_errors=True)
    share = os.path.join(APPDIR, SHARE)
    os.makedirs(os.path.join(share, "patch"))
    os.makedirs(DIST, exist_ok=True)

    copy_lf(os.path.join(LINUX, "AppRun"), os.path.join(APPDIR, "AppRun"))
    copy_lf(os.path.join(LINUX, "fractured-space-offline.desktop"),
            os.path.join(APPDIR, "fractured-space-offline.desktop"))
    png = png_from_ico(os.path.join(ROOT, "assets", "app.ico"))
    for name in ("fractured-space-offline.png", ".DirIcon"):
        open(os.path.join(APPDIR, name), "wb").write(png)

    copy_lf(os.path.join(LINUX, "fso_linux.py"), os.path.join(share, "fso_linux.py"))
    shutil.copyfile(os.path.join(ROOT, "server", "responses.json"), os.path.join(share, "responses.json"))
    shutil.copyfile(os.path.join(ROOT, "LICENSE"), os.path.join(share, "LICENSE"))
    for f in os.listdir(os.path.join(ROOT, "patch")):
        shutil.copyfile(os.path.join(ROOT, "patch", f), os.path.join(share, "patch", f))

    sqfs = os.path.join(OBJ, "app.squashfs")
    count, size = mksquashfs.build(APPDIR, sqfs, ["AppRun", SHARE + "/fso_linux.py"])
    print("squashfs: %d inodes, %.1f MB" % (count, size / 1e6))

    runtime = open(os.path.join(LINUX, "runtime-x86_64"), "rb").read()
    if runtime[:4] != b"\x7fELF" or runtime[8:11] != b"AI\x02":
        raise SystemExit("linux/runtime-x86_64 is not an AppImage type2 runtime")
    with open(OUT, "wb") as out:
        out.write(runtime)
        with open(sqfs, "rb") as fh:
            shutil.copyfileobj(fh, out)
    try:
        os.chmod(OUT, 0o755)
    except OSError:
        pass
    print("AppImage: %s (%.1f MB)" % (OUT, os.path.getsize(OUT) / 1e6))


if __name__ == "__main__":
    main()
