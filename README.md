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

The installer, launcher, F1 menu and project documentation are English-only, regardless of the system language.

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

### Co-op status

The launcher includes an experimental co-op admission flow. A host must allow inbound **TCP 8090** for join requests and **UDP 7777** for game traffic; the launcher binds these services to the selected local address. The host explicitly accepts each new guest. Accepted guest identities are saved locally and reused on later joins.

For Internet play, use a private VPN such as **Tailscale** (recommended) or ZeroTier so both players are on the same virtual LAN; this avoids exposing ports on a public router. On a direct Internet connection, forward TCP 8090 and UDP 7777 to the host PC. Do not expose other management ports.

The host can choose a party size of two to four humans and how many humans belong on the host's team. Approved guests are assigned to fill those team sizes, and the wrapper passes the selected team in the Unreal join URL. Team placement and bot rebalancing still depend on undocumented game behavior; a two-live-client team-assignment session has not been confirmed.

### Personal profiles and F1 menu

Each installation creates its own player identity. New profiles keep all ships unlocked and the recorded experience for level 68, with inherited combat statistics cleared. Supported statistic updates are saved under `profiles/<player-id>.json` in `%LOCALAPPDATA%/FracturedSpaceOffline`, or the Linux state directory. Live result events are saved locally and imported with duplicate protection. A full in-game match completion still needs validation.

On Windows, **F1** opens a menu rendered inside the game using DirectX 11. It includes personal profile controls and local-server trainer actions adapted from [Makichika's trainer](https://github.com/Makichika/Fractured-space-cheat-menu). Start a local match and wait for your ship to spawn before using combat controls. Co-op guests cannot modify the host server. Profile changes refresh on the next login. Combat controls and in-game rendering still need gameplay validation; runtime testing was blocked by tool approval review.

### Limitations
- Inventory and unlocks come from a recorded account. Personal combat history starts empty; supported profile updates are saved per player.
- The store and purchases do not work.
- To play online with the community, use the [Fractured Space Bootstrapper](https://github.com/Tigerhacker/fractured-bootstrapper). The offline launcher has its own app directory and marker, and reuses the shared game patch when its hashes match. If a different Bootstrapper patch is present, the installer stops instead of overwriting it.

## Repository layout

| Path | Contents |
|---|---|
| `src/Launcher/OfflineLauncher.cs` | Launcher with the built-in local Fireline server |
| `src/Launcher/CoopAdmission.cs`, `src/Launcher/UdpRelay.cs` | Experimental approved guest admission and UDP forwarding |
| `src/ServerWrapper/ServerWrapper.cs` | Wrapper for the game's dedicated server process |
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

Windows builds need the .NET Framework C# compiler and Visual Studio Build Tools with the Desktop development with C++ workload for the DirectX 11 F1 overlay.

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

## Community client updates

The installer and AppImage include the game-side fixes from [Makichika/Fractured-space-fixe-](https://github.com/Makichika/Fractured-space-fixe-): updated client executable, drafting UI, visual fixes and event content. Event modes and effect clocks need compatible server logic; Discord avatars need the online Bootstrapper avatar service and use fallback avatars offline. See `tools/makichika-lock.json` for the imported revision and `rules.md` for the update workflow.

## Credits and license

### The Expanse fleet test branch

The `expanse` branch includes seven converted ships in its Windows and Linux test installers, with separate native identities, default account ownership, source weapon assemblies and selector portraits. Live gameplay and balance remain under test. The [source review](mods/expanse/README.md) records attribution and per-asset licenses; [authoring instructions](mods/expanse/AUTHORING.md) explain rebuilding from the Git LFS payload and updating the assets. No public release has been published for this fleet.

| Ship | Model / texture credit | SpaceEngine adaptation | Declared graphics license |
| --- | --- | --- | --- |
| [MCRN Tachi (planned in-game name: Rocinante)](https://steamcommunity.com/sharedfiles/filedetails/?id=2211361535) | Anton Perfilev (`wintermute666`) | jamesmule | CC BY-NC-SA 4.0 |
| [Razorback](https://steamcommunity.com/sharedfiles/filedetails/?id=2224316655) | Chris Kuhn; CC0Textures.com | jamesmule; retro-visor | CC0 1.0 |
| [MCRN Donnager](https://steamcommunity.com/sharedfiles/filedetails/?id=2375119898) | Chris Kuhn; distributed by strawfinch | jamesmule; retro-visor | CC0 1.0 |
| [UNN Mayotte](https://steamcommunity.com/sharedfiles/filedetails/?id=2687045417) | Azzecco (`lux_comodo`) | jamesmule | CC BY-NC 4.0 |
| [MCRN Avalanche](https://steamcommunity.com/sharedfiles/filedetails/?id=2687094193) | Azzecco (`lux_comodo`) | jamesmule | CC BY-NC 4.0 |
| [Epstein's Yacht](https://steamcommunity.com/sharedfiles/filedetails/?id=2368610280) | Chris Kun as credited by the source; strawfinch / owlstraw | retro-visor | Conflicting CC0 / CC BY notices; mod-specific texture rights need clarification |
| [MCRN Chariot-Type Dropship](https://steamcommunity.com/sharedfiles/filedetails/?id=2375181309) | Chris Kuhn; distributed by strawfinch | jamesmule | CC0 1.0 |

The [fleet integration plan](mods/expanse/INTEGRATION_PLAN.md) records intended roles and remaining playtests. The authoring document records the implemented test loadouts and their limits.

The project's code license does not replace third-party graphics licenses. Source-derived television audio is excluded from any proposed import unless separately licensed. These credits do not imply endorsement.

- [Makichika/Fractured-space-fixe-](https://github.com/Makichika/Fractured-space-fixe-): community client fixes and assets.
- [Tigerhacker/refireline](https://github.com/Tigerhacker/refireline): Fireline emulator and recorded responses (GPL-3.0).
- [Tigerhacker/fractured-bootstrapper](https://github.com/Tigerhacker/fractured-bootstrapper): origin of the client patch included in `patch/`.
- [AppImage/type2-runtime](https://github.com/AppImage/type2-runtime): AppImage runtime (MIT).
- This project is licensed under **GPL-3.0** (see `LICENSE`).

Fractured Space is the property of its respective owners. This project is not affiliated with them. The `patch/` folder contains community-modified client files, included only to preserve the game.
