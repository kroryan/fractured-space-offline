# Fractured Space Offline

Play **Fractured Space** offline against bots, using a local server that emulates the official backend service (Fireline), which was shut down in 2019.

Everything needed is in this repository. The installer does not download anything.

## Installation

1. Install **Fractured Space** from Steam (free; it is still available in Steam libraries).
2. Download **`FracturedSpaceOfflineSetup.exe`** from [Releases](https://github.com/kroryan/fractured-space-offline/releases/latest).
3. Run it. Check that the game folder is correct (usually `...\steamapps\common\Space`; click *Browse* if it was not detected) and click **Install**.
4. Open **Fractured Space Bootstrapper Offline** from the Start menu or the desktop.
5. In game: **Play → Training → Solo vs AI**.

The installer:
- Applies the client patch to the game. The files are embedded in the installer (the `patch/` folder of this repository) and checked by SHA-256. The original files are backed up to `<game>\fractured-offline-backup`.
- Installs the launcher to `%LOCALAPPDATA%\Programs\fractured-space-bootstrapper-offline`.
- Creates shortcuts and an entry in *Settings → Apps* to uninstall it. When uninstalling, you can choose whether to restore the original game files.
- Tells Windows not to upscale the game on high-DPI screens.

It works fully offline and needs no administrator rights. It does not install certificates or modify the `hosts` file.

Windows SmartScreen may warn about the installer because it is not code-signed. Click *More info → Run anyway*.

The installer and launcher UI is in English, or in Spanish when Windows is set to Spanish.

## Linux (Steam Deck, desktop) — quick and dirty

A single **`FracturedSpaceOffline-x86_64.AppImage`** that finds your Fractured Space install and a Proton installation, patches the game and runs it offline.

1. Install **Fractured Space** from Steam, and a Proton version (for example *Proton 9.0*, from the *Tools* section of your Steam library). Running the game once from Steam creates its Proton prefix, which is recommended.
2. Download the AppImage from [Releases](https://github.com/kroryan/fractured-space-offline/releases/latest), then make it executable and run it:
   ```bash
   chmod +x FracturedSpaceOffline-x86_64.AppImage
   ./FracturedSpaceOffline-x86_64.AppImage
   ```
3. Optional: add it to your applications menu with `./FracturedSpaceOffline-x86_64.AppImage --install-desktop` (remove it with `--uninstall-desktop`).

Requirements: Python 3 (installed on almost every distro and on SteamOS). Steam libraries are detected in `~/.steam`, `~/.local/share/Steam`, Flatpak and Snap installs, including extra library folders. The newest Valve *Proton N.N* is used, then custom builds from `compatibilitytools.d`, then *Proton - Experimental*.

Overrides: `FSO_GAME_DIR=/path/to/steamapps/common/Space`, `FSO_PROTON=/path/to/Proton`, `FSO_PORT=8080`. The log is written to `~/.local/share/fractured-space-offline/requests.log`.

## How it works

```
FracturedSpaceBootstrapperOffline.exe
 ├─ local HTTP server on 127.0.0.1:8080   ← answers like api.fireteam.net (recorded responses)
 ├─ sets windowed fullscreen at the screen's native resolution
 └─ starts "Fractured Space.exe" -flhost=http://127.0.0.1:8080 -discord=offline
```

- The game needs the **Fireline** service to log in and to load the account, ships and progression.
- The patched game executable accepts `-flhost` to use a different server.
- The launcher contains a minimal emulator that serves recorded responses from the original service, based on [Tigerhacker/refireline](https://github.com/Tigerhacker/refireline).
- Requests made by the game are logged to `requests.log` in the install folder. Requests without a recorded response are marked `MISS`.

### Limitations
- The account is a **recorded** one, so progress is not saved between sessions.
- The store, purchases and multiplayer do not work.
- To play online with the community, use the [Fractured Space Bootstrapper](https://github.com/Tigerhacker/fractured-bootstrapper). Both can be installed together because they use the same patch.

## Repository layout

| Path | Contents |
|---|---|
| `src/Launcher/OfflineLauncher.cs` | Launcher with the built-in local Fireline server |
| `src/Launcher/README.txt` | Readme installed next to the launcher |
| `src/Installer/Installer.cs` | Graphical installer/uninstaller (applies the patch and installs the launcher) |
| `server/responses.json` | Recorded `api.fireteam.net` responses (from refireline) |
| `server/fireline_emu.py` | Alternative Python/Flask version of the server |
| `patch/` | Client patch files (modified game executable, `BP.pak` and UI scripts) |
| `linux/fso_linux.py` | Linux launcher: Steam/Proton detection, patching, local server |
| `linux/AppRun`, `linux/*.desktop` | AppImage entry point and desktop entry |
| `linux/mksquashfs.py` | Minimal SquashFS writer, so the AppImage can be built on any OS |
| `linux/build_appimage.py` | AppImage build script |
| `linux/runtime-x86_64` | AppImage type2 runtime (from AppImage/type2-runtime, release 20251108) |
| `assets/app.ico` | Application icon |
| `build.ps1` | Build script |

## Building

Only Windows is needed: the build uses the C# compiler that ships with .NET Framework 4.x.

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

This produces:
- `dist\FracturedSpaceOfflineSetup.exe`: the Windows installer, a single file that contains the launcher, the data and the patch.
- `dist\FracturedSpaceOffline-x86_64.AppImage`: the Linux build (needs Python 3 on the build machine).

The AppImage can also be built on its own, on any OS, with `python linux/build_appimage.py`.

### Python server (optional)

```bash
pip install flask
python server/fireline_emu.py        # http://127.0.0.1:8080
```

Then start the patched game:

```bat
set SteamAppId=310380
"...\Space\spacegame\Binaries\Win64\Fractured Space.exe" -flhost=http://127.0.0.1:8080 -discord=offline
```

## Credits and license

- [Tigerhacker/refireline](https://github.com/Tigerhacker/refireline): Fireline emulator and recorded responses (GPL-3.0).
- [Tigerhacker/fractured-bootstrapper](https://github.com/Tigerhacker/fractured-bootstrapper): origin of the client patch included in `patch/`.
- [AppImage/type2-runtime](https://github.com/AppImage/type2-runtime): AppImage runtime (MIT).
- This project is licensed under **GPL-3.0** (see `LICENSE`).

Fractured Space is the property of its respective owners. This project is not affiliated with them. The `patch/` folder contains community-modified client files, included only to preserve the game.
