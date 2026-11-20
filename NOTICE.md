# Included community work

The DirectX 11 overlay in `src/Overlay` adapts the F1 menu from the local Dreadnought Offline project (`C:/Users/PC/dreadnought-offline`). Third-party ImGui, kiero and MinHook licenses are retained in `src/Overlay/third_party` (including `minhook/LICENSE.txt`).

The trainer engine in `src/Trainer` comes from https://github.com/Makichika/Fractured-space-cheat-menu at `636ffc81915bea523a718e85d0ec6e94e11342e4`. Its memory layout checks and combat logic are retained. Local modifications replace the standalone dialog with an authenticated loopback bridge and restrict discovery to the offline launcher's configured original server executable. `tools/trainer-lock.json` records source hashes. The upstream README and security notice are included.

The client patches originate from Tigerhacker/fractured-bootstrapper and Makichika/Fractured-space-fixe-. See README.md, rules.md and tools/makichika-lock.json. The Fireline recorded response foundation originates from Tigerhacker/refireline (GPL-3.0).
