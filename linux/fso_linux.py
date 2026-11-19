#!/usr/bin/env python3
"""Fractured Space Offline - Linux launcher (quick and dirty).

- Finds the Fractured Space install in your Steam libraries
- Applies the client patch (from ../patch, verified by SHA-256; originals backed up)
- Finds a Proton installation to run the game with
- Runs a local Fireline emulator on http://127.0.0.1:8080 (recorded responses)
- Starts the game in windowed fullscreen and stops the server when it exits

Only needs Python 3.7+ (standard library). Environment overrides:
  FSO_GAME_DIR   path to the game folder (.../steamapps/common/Space)
  FSO_PROTON     path to a Proton folder or its 'proton' script
  FSO_PORT       local server port (default 8080)
"""
import glob
import hashlib
import http.server
import json
import os
import re
import shutil
import socketserver
import subprocess
import sys
import threading
import time

APP = "Fractured Space Offline"
APPID = "310380"
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("FSO_DATA_DIR", HERE)
PATCH_DIR = os.path.join(DATA_DIR, "patch")
RESPONSES = os.path.join(DATA_DIR, "responses.json")
STATE_DIR = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")),
                         "fractured-space-offline")
LOG = os.path.join(STATE_DIR, "requests.log")
PORT = int(os.environ.get("FSO_PORT", "8080"))
PREFIX = "https://api.fireteam.net/"
GAME_EXE_REL = "spacegame/Binaries/Win64/Fractured Space.exe"
BACKUP_DIR = "fractured-offline-backup"
PATCH_LEVEL = 30

PATCH = [
    ("Fractured Space.exe", GAME_EXE_REL, "fa6288c2d914366e14175c1d9ebbb459f6bd605c348b6148e9eea33d7290bc2a"),
    ("ClientConfig.json", "spacegame/ClientConfig.json", "0087a651ad5fbb235fa438b8d3a3f47cf2f6b11b3f88c528f82c48ccdc8d4b91"),
    ("startgame-script.js", "spacegame/Content/UIResources/frontend/views/startgame/startgame-script.js", "bac58eaa7f06a1b2401e5300e0141739055736bfb66d285e28b0096b83bcc1bb"),
    ("startgame-style.css", "spacegame/Content/UIResources/frontend/views/startgame/startgame-style.css", "49e856f3667e0c22db18a8c864c62ae66f1e1e2940d0efb783955ea6e0460301"),
    ("gamemodes-config.js", "spacegame/Content/UIResources/frontend/views/gamemodes/gamemodes-config.js", "7d864d2985f05b81cd37199c4150652c4becf9c5cc253f160c2f38d7db7509bd"),
    ("nsloctext.js", "spacegame/Content/UIResources/frontend/data/translations/nsloctext.js", "c1d43e513deb470d763b5d023db9275d3cde6bb689c45f1da110eb14ddd091af"),
    ("BP.pak", "spacegame/Content/Paks/BP.pak", "cac460fbce8a33e8f155b9a4abd14c15981156978b3a2d420dc2b468399d1681"),
    ("results-script.js", "spacegame/Content/UIResources/frontend/views/results/results-script.js", "ace5e5197f6779efd46531c0f08c6b2b7d963f3ee23533bcbea3c6ab7c710766"),
    ("hangar-script.js", "spacegame/Content/UIResources/frontend/views/hangar/hangar-script.js", "b3290327dfa2c94af87a58aa13b3021706f5685f249edbcd1a34bbb40ff8eede"),
]

log_lock = threading.Lock()


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    with log_lock:
        try:
            with open(LOG, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError:
            pass


def fail(msg):
    log("ERROR: " + msg)
    # Show a dialog when started from a desktop launcher (no terminal)
    for cmd in (["zenity", "--error", "--title", APP, "--text", msg],
                ["kdialog", "--title", APP, "--error", msg],
                ["notify-send", APP, msg]):
        if shutil.which(cmd[0]):
            try:
                subprocess.run(cmd, check=False)
                break
            except OSError:
                pass
    sys.exit(1)


# ---------------------------------------------------------------- Steam / game

def steam_roots():
    home = os.path.expanduser("~")
    cands = [
        os.path.join(home, ".steam", "root"),
        os.path.join(home, ".steam", "steam"),
        os.path.join(home, ".local", "share", "Steam"),
        os.path.join(home, ".var", "app", "com.valvesoftware.Steam", "data", "Steam"),
        os.path.join(home, ".var", "app", "com.valvesoftware.Steam", ".local", "share", "Steam"),
        os.path.join(home, "snap", "steam", "common", ".local", "share", "Steam"),
    ]
    seen, out = set(), []
    for c in cands:
        if os.path.isdir(os.path.join(c, "steamapps")):
            real = os.path.realpath(c)
            if real not in seen:
                seen.add(real)
                out.append(c)
    return out


def library_folders(root):
    libs = [os.path.join(root, "steamapps")]
    for vdf in (os.path.join(root, "steamapps", "libraryfolders.vdf"),
                os.path.join(root, "config", "libraryfolders.vdf")):
        try:
            with open(vdf, encoding="utf-8", errors="replace") as fh:
                for m in re.finditer(r'"path"\s+"([^"]+)"', fh.read()):
                    libs.append(os.path.join(m.group(1).replace("\\\\", "\\"), "steamapps"))
        except OSError:
            pass
    out, seen = [], set()
    for l in libs:
        r = os.path.realpath(l)
        if os.path.isdir(l) and r not in seen:
            seen.add(r)
            out.append(l)
    return out


def is_game_dir(p):
    return bool(p) and os.path.isdir(os.path.join(p, "spacegame", "Binaries", "Win64"))


def find_game(roots):
    env = os.environ.get("FSO_GAME_DIR")
    if env:
        if is_game_dir(env):
            return env, os.path.normpath(os.path.join(env, "..", ".."))
        fail("FSO_GAME_DIR does not look like the Fractured Space folder:\n" + env)
    for root in roots:
        for lib in library_folders(root):
            p = os.path.join(lib, "common", "Space")
            if is_game_dir(p):
                return p, lib
    return None, None


def proton_version_key(path):
    name = os.path.basename(os.path.dirname(path))
    nums = [int(n) for n in re.findall(r"\d+", name)]
    stable = 0 if "experimental" in name.lower() else 1  # prefer numbered releases
    return (stable, nums)


def find_proton(roots):
    env = os.environ.get("FSO_PROTON")
    if env:
        p = env if os.path.basename(env) == "proton" else os.path.join(env, "proton")
        if os.path.isfile(p):
            return p
        fail("FSO_PROTON does not point to a Proton install:\n" + env)
    found = []
    for root in roots:
        for lib in library_folders(root):
            found += glob.glob(os.path.join(lib, "common", "Proton*", "proton"))
        found += glob.glob(os.path.join(root, "compatibilitytools.d", "*", "proton"))
    for extra in ("/usr/share/steam/compatibilitytools.d", "/usr/local/share/steam/compatibilitytools.d"):
        found += glob.glob(os.path.join(extra, "*", "proton"))
    found = [f for f in found if os.path.isfile(f)]
    if not found:
        return None
    # Prefer Valve's numbered Proton, then GE/custom builds, then Experimental
    valve = [f for f in found if os.path.basename(os.path.dirname(f)).startswith("Proton ")]
    pool = valve or found
    return sorted(pool, key=proton_version_key)[-1]


# ---------------------------------------------------------------- patch

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def patch_game(game):
    log("Checking game patch...")
    backup = os.path.join(game, BACKUP_DIR)
    for src, rel, sha in PATCH:
        dest = os.path.join(game, rel)
        if os.path.isfile(dest) and sha256_file(dest) == sha:
            continue
        srcp = os.path.join(PATCH_DIR, src)
        if sha256_file(srcp) != sha:
            fail("Bundled patch file is corrupted: " + src)
        if os.path.isfile(dest):
            b = os.path.join(backup, rel)
            if not os.path.exists(b):
                os.makedirs(os.path.dirname(b), exist_ok=True)
                shutil.copy2(dest, b)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(srcp, dest)
        log("  patched " + src)
    with open(os.path.join(game, "bootlegger.json"), "w") as fh:
        fh.write('{"version":%d,"status":"ok"}' % PATCH_LEVEL)
    log("Patch OK (level %d)" % PATCH_LEVEL)


# ---------------------------------------------------------------- display

def screen_size():
    if shutil.which("xrandr"):
        try:
            out = subprocess.run(["xrandr", "--current"], capture_output=True, text=True, timeout=5).stdout
            m = re.search(r"^\S+ connected primary (\d+)x(\d+)", out, re.M) or \
                re.search(r"^\S+ connected (\d+)x(\d+)", out, re.M) or \
                re.search(r"current (\d+) x (\d+)", out)
            if m:
                return int(m.group(1)), int(m.group(2))
        except (OSError, subprocess.SubprocessError):
            pass
    return None


def configure_display(prefix):
    """Windowed fullscreen at the screen resolution (in the Proton prefix)."""
    cfg_dir = os.path.join(prefix, "pfx", "drive_c", "users", "steamuser", "AppData", "Local",
                           "spacegame", "Saved", "Config", "WindowsNoEditor")
    os.makedirs(cfg_dir, exist_ok=True)
    ini = os.path.join(cfg_dir, "GameUserSettings.ini")
    text = ""
    if os.path.isfile(ini):
        with open(ini, encoding="utf-8-sig", errors="replace") as fh:
            text = fh.read()
    section = "[/Script/spacegame.SpaceUserSettings]"
    if section not in text:
        text = text.rstrip() + ("\n\n" if text else "") + section + "\n"
    values = {"FullscreenMode": "1", "LastConfirmedFullscreenMode": "1", "PreferredFullscreenMode": "1"}
    size = screen_size()
    if size:
        w, h = map(str, size)
        values.update({"ResolutionSizeX": w, "ResolutionSizeY": h,
                       "LastUserConfirmedResolutionSizeX": w, "LastUserConfirmedResolutionSizeY": h,
                       "DesiredScreenWidth": w, "DesiredScreenHeight": h})
    for k, v in values.items():
        rx = re.compile(r"(?m)^" + re.escape(k) + r"=.*$")
        if rx.search(text):
            text = rx.sub(k + "=" + v, text)
        else:
            i = text.index(section) + len(section)
            text = text[:i] + "\n" + k + "=" + v + text[i:]
    with open(ini, "w", encoding="utf-8") as fh:
        fh.write(text)
    log("Display: windowed fullscreen" + (" %sx%s" % size if size else ""))


# ---------------------------------------------------------------- local Fireline server

CANNED, BY_PATH = {}, {}


def load_responses():
    with open(RESPONSES, encoding="utf-8") as fh:
        for e in json.load(fh):
            url = e["request"]["url"]
            path = url[len(PREFIX):] if url.startswith(PREFIX) else url
            path = path.split("?", 1)[0]
            item = (e["response"]["status_code"], e["response"]["content"].encode("utf-8"))
            CANNED[(e["request"]["method"], path)] = item
            BY_PATH[path] = item


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _handle(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        path, _, query = self.path.lstrip("/").partition("?")
        if not path:
            status, payload = 200, b"Fireline Emulator for Fractured Space (offline launcher)"
            log(self.command + " /")
        else:
            item = CANNED.get((self.command, path)) or BY_PATH.get(path)
            if item:
                status, payload = item
                log("hit  %s /%s" % (self.command, path))
            else:
                status, payload = 200, b"{}"
                log("MISS %s /%s%s %s" % (self.command, path, "?" + query if query else "",
                                          body[:200].decode("utf-8", "replace")))
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = _handle


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def start_server():
    load_responses()
    try:
        srv = Server(("127.0.0.1", PORT), Handler)
    except OSError as e:
        fail("Port %d is in use (is the offline launcher already running?)\n%s" % (PORT, e))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    log("Local server on http://127.0.0.1:%d" % PORT)
    return srv


# ---------------------------------------------------------------- main

def game_running():
    try:
        out = subprocess.run(["pgrep", "-f", "Fractured Space.exe"], capture_output=True, text=True).stdout
        return bool(out.strip())
    except OSError:
        return False


def main():
    os.makedirs(STATE_DIR, exist_ok=True)
    open(LOG, "w").close()
    if "--server-only" in sys.argv:
        start_server()
        while True:
            time.sleep(3600)

    roots = steam_roots()
    game, lib = find_game(roots)
    if not game:
        fail("Fractured Space was not found in your Steam libraries.\n"
             "Install it from Steam, or set FSO_GAME_DIR=/path/to/steamapps/common/Space")
    log("Game: " + game)
    if game_running():
        fail("Fractured Space is already running. Close it first.")

    proton = find_proton(roots)
    if not proton:
        fail("No Proton installation found.\n"
             "Install one from Steam (e.g. 'Proton 9.0' in the Tools section of your library), "
             "or set FSO_PROTON=/path/to/Proton")
    log("Proton: " + proton)

    try:
        patch_game(game)
    except PermissionError as e:
        fail("No permission to patch the game folder:\n%s" % e)

    compat = os.path.join(lib, "compatdata", APPID)
    os.makedirs(compat, exist_ok=True)
    try:
        configure_display(compat)
    except Exception as e:  # never block the launch on this
        log("Display config failed: %s" % e)

    srv = start_server()

    steam_root = roots[0] if roots else os.path.expanduser("~/.steam/root")
    env = dict(os.environ)
    env.update({
        "STEAM_COMPAT_DATA_PATH": compat,
        "STEAM_COMPAT_CLIENT_INSTALL_PATH": steam_root,
        "SteamAppId": APPID,
        "SteamGameId": APPID,
        "OPENSSL_ia32cap": ":~0x20000000",
    })
    exe = os.path.join(game, GAME_EXE_REL)
    # 'proton' is a Python script; run it directly if executable, else via python3
    runner = [proton] if os.access(proton, os.X_OK) else [sys.executable, proton]
    args = runner + ["run", exe,
                     "-flhost=http://127.0.0.1:%d" % PORT, "-discord=offline", "-culture=en-GB"]
    log("Starting game...")
    try:
        subprocess.run(args, cwd=os.path.dirname(exe), env=env)
    except OSError as e:
        fail("Could not start Proton:\n%s" % e)
    # The game can outlive the proton process; wait for it to close
    while game_running():
        time.sleep(3)
    srv.shutdown()
    log("Game closed.")


if __name__ == "__main__":
    main()
