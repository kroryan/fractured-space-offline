"""Proton launch support adapted from Tigerhacker/bootstrapper v2.0.1.

Keep container selection and Flatpak Steam's client-library HOME together.
No settings or game directories are created while resolving a launch.
"""
import json
import os
import re
import sys

RUNTIMES = {'1070560': 'SteamLinuxRuntime', '1391110': 'SteamLinuxRuntime_soldier',
            '1628350': 'SteamLinuxRuntime_sniper', '4183110': 'SteamLinuxRuntime_4'}


def vdf_value(path, key):
    try:
        with open(path, encoding='utf-8') as stream:
            match = re.search(r'"' + re.escape(key) + r'"\s*"([^"]+)"', stream.read(), re.I)
        return match.group(1) if match else None
    except OSError:
        return None


def case_path(path):
    """Resolve existing Steam paths without creating differently cased copies."""
    path = os.path.abspath(path)
    if os.path.exists(path):
        return path
    parent, name = os.path.split(path)
    if parent == path:
        return None
    parent = case_path(parent)
    if parent is None:
        return None
    try:
        matches = [entry for entry in os.listdir(parent) if entry.casefold() == name.casefold()]
    except OSError:
        return None
    return os.path.join(parent, matches[0]) if len(matches) == 1 else None


def launch_command(proton, libraries, game, game_args, environment, use_runtime=True):
    env = dict(environment)
    folder = os.path.dirname(proton)
    env.update({'STEAM_COMPAT_INSTALL_PATH': game, 'STEAM_COMPAT_APP_ID': '310380',
                'STEAM_COMPAT_TOOL_PATHS': folder, 'STEAM_COMPAT_LIBRARY_PATHS': ':'.join(libraries)})
    if env.get('APPIMAGE'):
        for name in ('LD_LIBRARY_PATH', 'LD_PRELOAD', 'PYTHONHOME', 'PYTHONPATH', 'GSETTINGS_SCHEMA_DIR'):
            env.pop(name, None)
    home = env.get('HOME', os.path.expanduser('~'))
    flatpak = os.path.join(home, '.var', 'app', 'com.valvesoftware.Steam')
    client = lambda root: os.path.isfile(os.path.join(root, '.steam', 'sdk64', 'steamclient.so'))
    if not client(home) and client(flatpak):
        env['HOME'] = flatpak
    executable = os.path.join(game, 'spacegame', 'Binaries', 'Win64', 'Fractured Space.exe')
    args = ['waitforexitandrun', case_path(executable) or executable] + game_args
    appid = vdf_value(os.path.join(folder, 'toolmanifest.vdf'), 'require_tool_appid')
    if appid and use_runtime:
        for library in libraries:
            name = vdf_value(os.path.join(library, 'appmanifest_' + appid + '.acf'), 'installdir') or RUNTIMES.get(appid)
            if not name:
                continue
            entry = case_path(os.path.join(library, 'common', name, '_v2-entry-point'))
            if entry and os.path.isfile(entry):
                return [entry, '--verb=waitforexitandrun', '--', proton] + args, env
        raise RuntimeError('Proton requires Steam Linux Runtime %s. Install it in Steam Tools, or select another Proton build. FSO_USE_RUNTIME=0 disables the container explicitly.' % appid)
    runner = [proton] if os.access(proton, os.X_OK) else [sys.executable, proton]
    return runner + args, env
