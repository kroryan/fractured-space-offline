# The Expanse ship source review

Status: the seven converted ships are included in the **test installer and AppImage**, with source-based weapon mounts and native selector portraits. Authoring, payload and class-loading checks are separate from live gameplay validation, which remains a user playtest. Development is published on the separate `expanse` branch; a public release is not yet authorized. The isolated Unreal 4.19.2 authoring project remains under ignored `obj/`; the redistributable cooked bundle is tracked in `payload/` as hash-checked binary parts. See [AUTHORING.md](AUTHORING.md) for rebuilding and validation.

The seven downloaded packages each contain one `.sss` ship definition and one `.sm` mesh. The inventory includes definitions inside ZIP-based `.pak` files; no additional ship variants were found in these downloads. See `source-manifest.json` for paths, byte counts and SHA-256 hashes. The source spells the yacht name "Epstein's Yatch"; the display name in this review uses "Yacht".

The planned in-game display name for the Tachi asset is **Rocinante**, preserving the source model and original credits. See the [integration and balance plan](INTEGRATION_PLAN.md).

## Attribution and declared licenses

| Ship / Workshop source | Original model and texture credit | SpaceEngine adaptation credit | Declared graphics license / review status |
| --- | --- | --- | --- |
| [MCRN Tachi](https://steamcommunity.com/sharedfiles/filedetails/?id=2211361535) | Anton Perfilev (`wintermute666`), [original model](https://sketchfab.com/3d-models/mcrn-tachi-5cc7b9ac82db44a18aa9d37afe1498d2) | jamesmule | [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/): attribution, noncommercial use and ShareAlike for adapted graphics. |
| [Razorback](https://steamcommunity.com/sharedfiles/filedetails/?id=2224316655) | Chris Kuhn; additional textures from CC0Textures.com | jamesmule and retro-visor | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) as declared on the Workshop page. |
| [MCRN Donnager](https://steamcommunity.com/sharedfiles/filedetails/?id=2375119898) | Chris Kuhn; model distributed by strawfinch on [Sketchfab](https://sketchfab.com/3d-models/mcrn-donnager-the-expanse-05e9f9006d914fcd96e95fbd452aaa28) | jamesmule and retro-visor | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) as declared on the Workshop page. |
| [UNN Mayotte](https://steamcommunity.com/sharedfiles/filedetails/?id=2687045417) | [Azzecco (`lux_comodo`)](https://sketchfab.com/lux_comodo) | jamesmule | [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/), not BY-NC-SA. |
| [MCRN Avalanche](https://steamcommunity.com/sharedfiles/filedetails/?id=2687094193) | [Azzecco (`lux_comodo`)](https://sketchfab.com/lux_comodo) | jamesmule | [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/), confirmed from the Steam published-file details API. |
| [Epstein's Yacht](https://steamcommunity.com/sharedfiles/filedetails/?id=2368610280) | Chris Kun as credited by the source; original model distributed by strawfinch / owlstraw | retro-visor | Needs clarification: the [Sketchfab model](https://sketchfab.com/3d-models/epsteins-yacht-the-expanse-137498e7aabb47dfaee3fe2652fadefa) describes CC0 but displays CC Attribution metadata. The Workshop page does not state a license for its modified texture. Do not assume the complete mod is CC0. |
| [MCRN Chariot-Type Dropship](https://steamcommunity.com/sharedfiles/filedetails/?id=2375181309) | Chris Kuhn; model distributed by strawfinch | jamesmule | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) as declared by the source publisher. |

These are the source publishers' license declarations, not a guarantee that they control every underlying right. The model licenses do not establish permission to redistribute recordings from the television series. Show-derived audio must be excluded from an import unless separately licensed. Existing game audio can be referenced instead. Credits do not imply endorsement by the artists, SpaceEngine or The Expanse rights holders.

The GPL-3.0 license for this project's code does not relicense third-party graphics. Any distributed graphics must have their own license notices, source links, original credits and a record of conversion/modification. Local conversions include coordinate/unit conversion, material translation and triangle reduction for runtime use. Yacht textures are excluded from the local conversion and replaced with a newly authored neutral material while their redistribution rights remain unresolved.

The requested Razorback light-cannon retrofit uses separate, scaled Tachi PDC
meshes and their texture by Anton Perfilev (`wintermute666`), adapted by
jamesmule. These adapted weapon assets retain **CC BY-NC-SA 4.0** and the
Rocinante/Tachi source credits above; the original Razorback hull remains
separate CC0 content. Its new mounting collar is project-authored CC0 geometry.

## Technical requirements before integration

The SpaceEngine packages use ZIP archives containing `SM02` meshes, material scripts, textures and ship definitions. They are not Unreal PAKs and cannot be installed unchanged into Fractured Space. The game's local logs identify Unreal Engine 4.19.2; its existing PAKs use the Unreal PAK format. See [SpaceEngine's ship format documentation](https://spaceengine.org/manual/making-addons/creating-a-ship/) and [Epic's UE4 cooking documentation](https://dev.epicgames.com/documentation/unreal-engine/content-cooking?application_version=4.27).

Required work:

1. Resolve asset-specific redistribution rights, including the yacht's conflicting notices. Retain license text and attribution with any converted assets.
2. Convert SM02 meshes and materials, validate scale/orientation and optimize the larger models. The published SM01 documentation alone is insufficient to assume an SM02 parser is correct.
3. Author and cook assets with a toolchain compatible with the game's Unreal 4.19.2 build. The installed editor and isolated project are now available; import success alone does not establish cooked runtime compatibility.
4. Implement compatible client/server ship definitions: visuals, collision, weapon attachment points, movement, loadouts, UI and spawn registration. A model by itself is not a playable ship.
5. Register each successfully integrated ship in the local account's default ownership, preserving the existing fleet. Merely adding fictional licenses to `responses.json` does not create a ship the client can load.
6. Verify hangar selection, player/bot spawning, solo/co-op behavior and installer/uninstaller handling, then build and publish a stable release with the actual cooked assets.

## Repeatable source inventory

Run from the repository root after Steam finishes downloading:

```powershell
python tools/audit_expanse.py --output mods/expanse/source-manifest.json
```

Use `--workshop-root` for a different Steam library. The scanner reads every loose and archived `.sss` definition and `.sm` mesh in the seven selected packages, and hashes every source file. It does not extract archives into the game or silently turn source files into installable content. Review additional packages and add their source IDs and license evidence before expanding the inventory.
