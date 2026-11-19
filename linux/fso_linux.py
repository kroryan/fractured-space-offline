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
import base64
import hashlib
import http.server
import ipaddress
import json
import os
import re
import shutil
import socket
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
RECORDED_IDENTITY = "197a97fc-4179-43f4-b009-9432ac0c8e53"
ACTIVE_IDENTITY = os.environ.get("FSO_PLAYER_ID", RECORDED_IDENTITY)
GAME_EXE_REL = "spacegame/Binaries/Win64/Fractured Space.exe"
BACKUP_DIR = "fractured-offline-backup"
SERVER_EXE_REL = "spacegame/Binaries/Win64/spserver.exe"
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


def choose_mode():
    """Remember and present the launcher start screen using desktop-native dialogs."""
    state = os.path.join(STATE_DIR, "launcher-mode")
    try:
        with open(state, encoding="utf-8") as fh:
            last = fh.read().strip()
    except OSError:
        last = "solo"
    labels = ["Play solo vs bots", "Create co-op game", "Join co-op game"]
    if shutil.which("zenity"):
        try:
            p = subprocess.run(["zenity", "--list", "--radiolist", "--title=" + APP,
                                "--text=Choose a game mode", "--column=", "--column=Mode",
                                "TRUE" if last == "solo" else "FALSE", labels[0],
                                "TRUE" if last == "host" else "FALSE", labels[1],
                                "TRUE" if last == "join" else "FALSE", labels[2]],
                               capture_output=True, text=True)
            if p.returncode:
                return None
            mode = {labels[0]: "solo", labels[1]: "host", labels[2]: "join"}.get(p.stdout.strip())
        except OSError:
            mode = "solo"
    elif shutil.which("kdialog"):
        p = subprocess.run(["kdialog", "--title", APP, "--radiolist", "Choose a game mode",
                            labels[0], "solo", "on" if last == "solo" else "off",
                            labels[1], "host", "on" if last == "host" else "off",
                            labels[2], "join", "on" if last == "join" else "off"], capture_output=True, text=True)
        if p.returncode:
            return None
        mode = p.stdout.strip()
    else:
        log("No zenity/kdialog found; defaulting to solo mode.")
        return "solo"
    if mode:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(state, "w", encoding="utf-8") as fh:
            fh.write(mode)
    if mode == "join":
        if shutil.which("zenity"):
            p = subprocess.run(["zenity", "--entry", "--title=" + APP, "--text=Host IP address"], capture_output=True, text=True)
            if p.returncode:
                return None
            os.environ["FSO_COOP_HOST"] = p.stdout.strip()
        elif shutil.which("kdialog"):
            p = subprocess.run(["kdialog", "--title", APP, "--inputbox", "Host IP address"], capture_output=True, text=True)
            if p.returncode:
                return None
            os.environ["FSO_COOP_HOST"] = p.stdout.strip()
        else:
            fail("Install zenity or kdialog to enter the host IP.")
    if mode == "host":
        addresses = local_ipv4_addresses()
        if addresses and shutil.which("zenity"):
            p = subprocess.run(["zenity", "--list", "--radiolist", "--title=" + APP,
                                "--text=Choose the address guests will connect to", "--column=", "--column=Address",
                                *sum((["TRUE" if i == 0 else "FALSE", a] for i, a in enumerate(addresses)), [])],
                               capture_output=True, text=True)
            if p.returncode: return None
            os.environ["FSO_BIND_HOST"] = p.stdout.strip().split()[0]
        elif addresses:
            os.environ["FSO_BIND_HOST"] = addresses[0].split()[0]
        if shutil.which("zenity"):
            same = subprocess.run(["zenity", "--question", "--title=" + APP,
                                   "--text=Should human players be on the same team?" ]).returncode == 0
            os.environ["FSO_SAME_TEAM"] = "1" if same else "0"
        elif shutil.which("kdialog"):
            same = subprocess.run(["kdialog", "--yesno", "Should human players be on the same team?", "--title", APP]).returncode == 0
            os.environ["FSO_SAME_TEAM"] = "1" if same else "0"
    return mode


def local_ipv4_addresses():
    """Return local IPv4 interfaces with VPN adapters ordered before LAN."""
    try:
        out = subprocess.run(["ip", "-o", "-4", "addr", "show", "scope", "global"],
                             capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    items = []
    for line in out.splitlines():
        m = re.search(r"\d+:\s+([^ ]+)\s+inet\s+(\d+\.\d+\.\d+\.\d+)", line)
        if not m: continue
        name, ip = m.groups()
        vpn = name.lower().startswith(("tailscale", "zt", "ham", "radmin"))
        try:
            addr = ipaddress.ip_address(ip)
            vpn = vpn or addr in ipaddress.ip_network("100.64.0.0/10") or addr in ipaddress.ip_network("25.0.0.0/8") or addr in ipaddress.ip_network("26.0.0.0/8") or addr in ipaddress.ip_network("192.168.191.0/24") or addr in ipaddress.ip_network("192.168.192.0/24") or addr in ipaddress.ip_network("10.147.0.0/16")
        except ValueError:
            pass
        items.append((0 if vpn else 1, name, ip))
    items.sort()
    return ["%s  (%s)" % (ip, name) for _, name, ip in items]


class AdmissionServer:
    """TCP join-only service. It has no remote account or server admin API."""
    def __init__(self, state_file):
        self.state_file = state_file
        try:
            with open(state_file, encoding="utf-8") as fh:
                self.guests = json.load(fh)
        except (OSError, ValueError):
            self.guests = {}
        self.allowed = set()
        self.lock = threading.Lock()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((os.environ.get("FSO_BIND_HOST", "0.0.0.0"), 8090)); self.sock.listen(16); self.sock.settimeout(1)
        self.running = True
        threading.Thread(target=self._serve, daemon=True).start()

    def _approval(self, peer):
        msg = "Player %s requests to join. Accept?" % peer
        try:
            if shutil.which("zenity"):
                return subprocess.run(["zenity", "--question", "--title=" + APP, "--text=" + msg]).returncode == 0
            if shutil.which("kdialog"):
                return subprocess.run(["kdialog", "--yesno", msg, "--title", APP]).returncode == 0
        except OSError:
            pass
        return False

    def _serve(self):
        while self.running:
            try: conn, addr = self.sock.accept()
            except socket.timeout: continue
            except OSError: return
            threading.Thread(target=self._handle, args=(conn, addr), daemon=True).start()

    def _handle(self, conn, addr):
        with conn:
            try:
                conn.settimeout(30)
                raw = conn.makefile("rb").readline(4097)
                if len(raw) > 4096: return
                req = json.loads(raw.decode("utf-8"))
                if req.get("op") != "join": return
                prior = req.get("id", "")
                with self.lock: ident = self.guests.get(prior)
                peer = addr[0]
                if not ident and not self._approval(peer):
                    conn.sendall(b'{"status":"rejected","id":""}\n'); return
                ident = ident or str(__import__("uuid").uuid4())
                with self.lock:
                    self.guests[ident] = ident; self.allowed.add(peer)
                    os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
                    with open(self.state_file, "w", encoding="utf-8") as fh: json.dump(self.guests, fh)
                conn.sendall((json.dumps({"status":"accepted", "id":ident}) + "\n").encode())
            except Exception as exc:
                log("Join request error: %s" % exc)

    def is_allowed(self, peer):
        with self.lock: return peer in self.allowed

    def close(self):
        self.running = False
        try: self.sock.close()
        except OSError: pass


class UdpRelay:
    def __init__(self, admission):
        self.admission = admission
        self.routes = {}; self.lock = threading.Lock(); self.running = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((os.environ.get("FSO_BIND_HOST", "0.0.0.0"), 7777)); self.sock.settimeout(1)
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while self.running:
            try: data, addr = self.sock.recvfrom(65535)
            except socket.timeout: continue
            except OSError: return
            if not self.admission.is_allowed(addr[0]): continue
            with self.lock:
                upstream = self.routes.get(addr)
                if upstream is None:
                    upstream = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    upstream.bind(("0.0.0.0", 0)); upstream.settimeout(1)
                    self.routes[addr] = upstream
                    threading.Thread(target=self._upstream, args=(upstream, addr), daemon=True).start()
            try: upstream.sendto(data, ("127.0.0.1", 7777))
            except OSError: pass

    def _upstream(self, upstream, peer):
        while self.running:
            try: data, _ = upstream.recvfrom(65535)
            except socket.timeout: continue
            except OSError: return
            try: self.sock.sendto(data, peer)
            except OSError: return

    def close(self):
        self.running = False
        try: self.sock.close()
        except OSError: pass
        with self.lock:
            for upstream in self.routes.values():
                try: upstream.close()
                except OSError: pass
            self.routes.clear()


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
    wrapper_src = os.path.join(DATA_DIR, "spserver-wrapper.exe")
    server = os.path.join(game, SERVER_EXE_REL)
    if os.path.isfile(wrapper_src) and os.path.isfile(server):
        server_dir = os.path.dirname(server)
        original = os.path.join(server_dir, "spserver_original.exe")
        saved = os.path.join(backup, SERVER_EXE_REL)
        if not os.path.isfile(original):
            os.makedirs(os.path.dirname(saved), exist_ok=True)
            if not os.path.isfile(saved): shutil.copy2(server, saved)
            shutil.copy2(server, original)
        shutil.copy2(wrapper_src, server)
        log("Installed co-op server wrapper (original backed up).")
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
                if ACTIVE_IDENTITY != RECORDED_IDENTITY:
                    text = payload.decode("utf-8", "replace").replace(RECORDED_IDENTITY, ACTIVE_IDENTITY)
                    def rewrite_jwt(match):
                        try:
                            part = match.group(1)
                            part += "=" * ((4 - len(part) % 4) % 4)
                            decoded = base64.urlsafe_b64decode(part.encode()).decode().replace(RECORDED_IDENTITY, ACTIVE_IDENTITY)
                            return "eyJhbGciOiJIUzI1NiJ9." + base64.urlsafe_b64encode(decoded.encode()).decode().rstrip("=") + "."
                        except Exception:
                            return match.group(0)
                    text = re.sub(r"eyJhbGciOiJIUzI1NiJ9\.([A-Za-z0-9_-]+)\.", rewrite_jwt, text)
                    payload = text.encode("utf-8")
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

    mode = choose_mode()
    if mode is None:
        return
    if mode != "solo" and not os.path.isfile(os.path.join(DATA_DIR, "spserver-wrapper.exe")):
        fail("This AppImage was built without spserver-wrapper.exe. Rebuild it with build.ps1 on Windows to enable co-op.")
    identity_file = os.path.join(STATE_DIR, "player-id")
    player_id = ""
    try:
        with open(identity_file, encoding="utf-8") as fh: player_id = fh.read().strip()
    except OSError:
        pass
    admission = relay = None
    if mode == "host":
        admission = AdmissionServer(os.path.join(STATE_DIR, "approved-guests.json"))
        try: relay = UdpRelay(admission)
        except OSError as e:
            admission.close(); fail("Could not open UDP 7777 for co-op: %s" % e)
        log("Co-op admission listening on TCP 8090; approved UDP relay on 7777")
    elif mode == "join":
        try:
            with socket.create_connection((os.environ["FSO_COOP_HOST"], 8090), timeout=120) as client:
                client.sendall((json.dumps({"op":"join", "id":player_id}) + "\n").encode())
                response = json.loads(client.makefile("rb").readline().decode())
            if response.get("status") != "accepted": fail("The host rejected the join request.")
            player_id = response["id"]
            with open(identity_file, "w", encoding="utf-8") as fh: fh.write(player_id)
        except Exception as e:
            fail("Could not join host on TCP 8090:\n%s" % e)
    global ACTIVE_IDENTITY
    ACTIVE_IDENTITY = player_id or RECORDED_IDENTITY

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
        "FSO_PLAYER_ID": player_id or RECORDED_IDENTITY,
    })
    if mode == "host":
        env["FSO_COOP_MODE"] = "host"
        env["FSO_SERVER_URL_EXTRA"] = "?coop=" + os.environ.get("FSO_SAME_TEAM", "1")
        env["FSO_BIND_HOST"] = os.environ.get("FSO_BIND_HOST", "0.0.0.0")
    if mode == "join":
        env["FSO_COOP_MODE"] = "guest"
        env["FSO_COOP_HOST"] = os.environ["FSO_COOP_HOST"]
    exe = os.path.join(game, GAME_EXE_REL)
    # 'proton' is a Python script; run it directly if executable, else via python3
    runner = [proton] if os.access(proton, os.X_OK) else [sys.executable, proton]
    args = runner + ["run", exe,
                     "-flhost=http://127.0.0.1:%d" % PORT, "-discord=offline", "-culture=en-GB"]
    log("Starting game...")
    progress = None
    if shutil.which("zenity"):
        progress = subprocess.Popen(["zenity", "--progress", "--title=" + APP, "--text=Preparing Proton…",
                                     "--percentage=15", "--auto-close", "--no-cancel"],
                                    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    text=True)
    try:
        if progress and progress.stdin:
            progress.stdin.write("45\nStarting Proton…\n75\nWaiting for game window…\n"); progress.stdin.flush()
        game_proc = subprocess.Popen(args, cwd=os.path.dirname(exe), env=env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Keep the splash only through startup, not for the whole play session.
        deadline = time.time() + 180
        while time.time() < deadline and game_proc.poll() is None and not game_running():
            time.sleep(0.5)
        if progress:
            try:
                progress.stdin.close()
                progress.wait(timeout=2)
            except Exception:
                progress.kill()
            progress = None
        game_proc.wait()
    except OSError as e:
        fail("Could not start Proton:\n%s" % e)
    finally:
        if progress:
            try:
                progress.stdin.close()
                progress.wait(timeout=2)
            except Exception:
                progress.kill()
    # The game can outlive the proton process; wait for it to close
    while game_running():
        time.sleep(3)
    srv.shutdown()
    if relay: relay.close()
    if admission: admission.close()
    log("Game closed.")


if __name__ == "__main__":
    main()
