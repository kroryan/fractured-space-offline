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
import argparse
import json

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
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--local-fleet', action='store_true')
    args = parser.parse_args()
    if os.path.commonpath([os.path.realpath(APPDIR), os.path.realpath(OBJ)]) != os.path.realpath(OBJ):
        raise SystemExit('AppDir resolved outside the local obj directory')
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

    shutil.copyfile(os.path.join(LINUX, "profile_store.py"), os.path.join(share, "profile_store.py"))
    copy_lf(os.path.join(LINUX, "fso_linux.py"), os.path.join(share, "fso_linux.py"))
    fleet_folder = os.path.join(OBJ, 'expanse-authoring')
    if not os.path.isfile(os.path.join(fleet_folder, 'fleet-manifest.json')):
        fleet_folder = os.path.join(ROOT, 'mods', 'expanse', 'payload')
    if args.local_fleet and not os.path.isfile(os.path.join(fleet_folder, 'FSO_Expanse_Experimental_P.pak')):
        import subprocess
        subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'restore_expanse_payload.py')], check=True)
    response_source = os.path.join(fleet_folder, 'candidate-responses.json') if args.local_fleet else os.path.join(ROOT, 'server', 'responses.json')
    shutil.copyfile(response_source, os.path.join(share, "responses.json"))
    shutil.copyfile(os.path.join(ROOT, "LICENSE"), os.path.join(share, "LICENSE"))
    wrapper = os.path.join(OBJ, "spserver-wrapper.exe")
    if os.path.isfile(wrapper):
        shutil.copyfile(wrapper, os.path.join(share, "spserver-wrapper.exe"))
    for f in os.listdir(os.path.join(ROOT, "patch")):
        shutil.copyfile(os.path.join(ROOT, "patch", f), os.path.join(share, "patch", f))
    if args.local_fleet:
        shutil.copyfile(os.path.join(fleet_folder, 'fleet-manifest.json'), os.path.join(share, 'fleet-manifest.json'))
        for entry in json.load(open(os.path.join(fleet_folder, 'fleet-manifest.json'), encoding='utf-8')):
            shutil.copyfile(os.path.join(fleet_folder, entry['src']), os.path.join(share, 'patch', entry['src']))

    sqfs = os.path.join(OBJ, "app.squashfs")
    count, size = mksquashfs.build(APPDIR, sqfs, ["AppRun", SHARE + "/fso_linux.py"])
    print("squashfs: %d inodes, %.1f MB" % (count, size / 1e6))

    runtime = open(os.path.join(LINUX, "runtime-x86_64"), "rb").read()
    if runtime[:4] != b"\x7fELF" or runtime[8:11] != b"AI\x02":
        raise SystemExit("linux/runtime-x86_64 is not an AppImage type2 runtime")
    output = os.path.join(DIST, 'FracturedSpaceOffline-ExpanseTest-x86_64.AppImage') if args.local_fleet else OUT
    with open(output, "wb") as out:
        out.write(runtime)
        with open(sqfs, "rb") as fh:
            shutil.copyfileobj(fh, out)
    try:
        os.chmod(output, 0o755)
    except OSError:
        pass
    print("AppImage: %s (%.1f MB)" % (output, os.path.getsize(output) / 1e6))


if __name__ == "__main__":
    main()
