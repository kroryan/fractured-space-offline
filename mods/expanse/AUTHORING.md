# Local fleet authoring

All outputs below are experimental until native game validation passes. They
must not be copied into the installed game or presented as a finished test
installer. Publication and Git push are currently disabled by the user's request.

## Tools and source preparation

The source review is recorded in `source-manifest.json`. Run
`python tools/prepare_expanse.py --help` for the local conversion entry point.
`tools/expanse_sm.py` decodes the inspected SM02 vertex layouts, including packed
positions, UVs and normals. Run its regression checks with:

```powershell
python -m unittest discover -s tests -p test_expanse_sm.py
```

The Blender export script takes a prepared metadata file after `--`. Set
`EXPANSE_TRIANGLE_BUDGET` to bound runtime geometry before FBX export. The current
capital-ship budget is 350,000 triangles. This is a provisional performance
budget, not a measured quality/performance result. Original source meshes remain
available locally; reduced hulls require visual review at gameplay distances.

Use `--python-exit-code 1` with Blender so Python failures propagate to the build.

## Unreal import and cooking

`python tools/create_expanse_project.py --ship WORKSHOP_ID` writes the isolated
content-only project and native ImportAssets settings under
`obj/expanse-authoring/UnrealProject`. The project uses Unreal 4.19.2. Set the
process environment `OPENSSL_ia32cap=:~0x20000000` before starting the editor on
this machine. Use `-nullrhi -unattended -nop4 -nosplash` for commandlets.

The seven hulls have imported successfully. WindowsNoEditor cooking completed
with zero errors and warnings in `obj/expanse-authoring/unreal-cook.log`.
This establishes cooker compatibility, not compatibility with Fractured Space's
native runtime classes or ship database.

## Native class adaptation

`tools/FleetAssetTool` uses the MIT-licensed UAssetAPI NuGet package 1.1.0.
Its `dump`, `clone` and `vectors` commands operate on local UE4.19 assets.
`tools/build_expanse_assets.ps1` generates independent hull-part, system and
ship-data classes from inspected stock assets. The source assets and decrypted
inspection data remain under ignored `obj/expanse-review`.

`python tools/build_expanse_fleet.py` creates seven deterministic ship identities
and definitions under `obj/expanse-authoring/patch-content/Content/Ships`.
These definitions currently inherit stock loadouts. The military-specific
weapons and unarmed civilian restrictions must be implemented before claiming
that the fleet is ready for gameplay.

The Rocinante attachment positions in `attachments/rocinante.json` are provisional
authoring coordinates. The vector editor writes and reloads actual FVector
properties; no in-game placement or articulated source turret validation has
passed. Remaining ships still need hull-specific attachment layouts, collision,
damage locations, effect placement and balance.

## Experimental packaging

After successful cooking, run `python tools/package_expanse_local.py`.
It builds and tests `obj/expanse-authoring/FSO_Expanse_Experimental_P.pak` using
the installed UnrealPak. The PAK has new content paths; existing stock ship
definitions are not overwritten. Its integrity test does not exercise gameplay.

Next gates are isolated native runtime loading, ship discovery/selection,
weapons and articulation, damage/effects, default ownership, and mandatory
installer payload integration on both platforms. Existing files in `dist/`
predate this integration and must not be described as fleet-enabled binaries.

## Native runtime evidence

`tools/stage_expanse_runtime.ps1` creates an isolated staging tree with copied
binaries and the experimental PAK. Its stock-content links are inputs only:
never run an installer or content authoring command against that tree.

The headless lobby smoke test passed with `FSO_GAME_DIR` pointing at this tree.
`tests/Smoke-ExpanseClassLoading.ps1` also resolved all seven generated system
classes through the native game executable. The probe intentionally passes a
ship-system class to the game-mode resolver; its expected type rejection proves
that the BlueprintGeneratedClass was found and deserialized. It does not mean
that a ship spawned or that its weapons, account ownership or hangar entry work.
Evidence is under `obj/expanse-authoring/class-probes`.

An additional compatibility concern found during inspection is the inherited
`StaticMeshSkin` material replacement data: stock replacements refer to stock
material slots and must be adapted or cleared for each new hull before enabling
cosmetic variants. No stock cosmetic compatibility has been validated.

## Candidate hangar and account catalog

`python tools/build_expanse_catalog.py` creates
`obj/expanse-authoring/candidate-responses.json` with 43 catalog ships, cloned
part trees and matching local ownership licenses. The recorded blob uses raw
DEFLATE behind a zlib header with a non-Adler trailer; the candidate emits a
standard zlib stream and validates the decompressed size.

`python -m unittest discover -s tests -p test_expanse_catalog.py` checks the
candidate against native definition GUIDs, reachable part references and account
ownership. This passed locally. The candidate remains separate from shipping
`server/responses.json` until client validation and installer integration.

Initial positive hull/energy values live in `balance/` and are applied to
independent ship-data classes by the `tune` command. They are provisional,
unmeasured gameplay values. Civilian definitions omit weapon and fighter-bay
systems; Rocinante omits inherited railgun, beam and fighter systems. Those
definition changes still require runtime spawn and weapon/effect checks.

The local Windows installer build path now accepts `build.ps1 -LocalFleet`.
This is a build-time selection for the maintainer, not an installer component
choice: the embedded fleet manifest is appended to the normal mandatory patch
list. It embeds the candidate account responses together with the PAK and its
SHA-256 manifest. Do not run this build as a finished deliverable before the
remaining runtime checks and asset notices are complete. The installer source
has passed a .NET Framework compilation check with this manifest loader.

Source CFG main-drive positions exposed different forward axes among the mods.
`rebuild_expanse_models.ps1` re-exports them with per-source axis conversion and
reimports/cooks them. `-SkipExport` repeats only import/cooking when settings
change. The importer now explicitly requests Unreal X-forward and assigns
provisional gameplay envelopes of 300–1500 native units to keep the imported
fleet readable alongside stock ships. Attachment and camera placement must be
checked against the resulting imported bounds, rather than guessed FBX units.

After fresh-package import, Donnager's measured Unreal bounds were 1500 by
571.08 by 571.08 native units with its long axis on X. This confirms the new
scale/orientation settings apply; atomic reimport had retained the old settings.

`prepare_expanse_drives.py` reads main-drive positions from each source CFG,
preferring nozzle glow centers over offset plume volumes. The native effect
mapping now assigns one drive for Rocinante, Avalanche, Razorback and Yacht,
four for Donnager and six for Mayotte. Extra inherited particle templates are
disabled. Chariot has hover/chemical thrusters rather than a main drive and
still requires its own effect placement and orientation.

Armour requires a separate six-region mesh: native armour meshes have six
material slots, whereas imported visuals have unrelated material layouts.
The Blender exporter now creates `SM_ARM_EXP_*.fbx` with explicit front/rear,
left/right and top/bottom regions. This preserves independent native damage
entries; the final region behavior still needs in-game verification. The PAK
packager refuses to package a fleet missing any of its seven cooked armour meshes.

## Hangar rendering crash regression

The first Windows test crashed on selecting Avalanche after the native log
reported successful ship construction. The render thread could not find
`TBasePassVSFPrecomputedVolumetricLightmapLightingPolicy` for material
`The_Expanse_MCRN_Avalanche_P10`. The authoring project had disabled static
lighting, which strips that shader permutation. Native headless class loading
cannot detect this rendering failure.

The project now enables static lighting and low-quality lightmap support before
cooking. A full recook completed with zero errors/warnings. The old packaged P10
material lacked the shader reference; the recooked material contains it.
`FleetAssetTool check-lighting` verified the required shader reference in all
261 cooked fleet materials. Packaging now runs this check as a required gate.
Actual hangar rendering and combat remain separate runtime tests.

## Original weapon geometry and firing groups

`blender_rocinante_pdc.py` removes the six original moving PDC assemblies from
the hull before exporting separate gun/swivel meshes. The native bindings in
`build_rocinante_pdc.py` retain the six source mounting pivots, two mirrored
gun variants, and native yaw/pitch components. No stock cannon model should
remain on that hull. The battery allows up to six eligible turrets; surface
arcs determine which can bear on a target.

`inspect_ship_components.py 2375119898` inventories Donnager's original
connected geometry. `blender_donnager_railguns.py` separates 437 complete
components per railgun (63,447 port and 63,448 starboard triangles), removing
those exact triangles from the hull. Each gun has its own cooked muzzle
socket. `build_donnager_weapons.py` replaces the inherited Colossus placements
with two graded railgun mounts, a two-part native weapon subsystem admitting
two concurrent guns, and six launch positions at the original bow tube lips.
The launch-tube component IDs are 6128, 6129, 7349, 7350, 8135 and 8136.
These authoring checks do not prove that both guns actually fire in-game.
The original model's small details have not been approved as PDC barrels;
do not assign a weapon count from repeated greebles.

The user explicitly requested an armed Razorback after the first test.
`blender_razorback_weapon.py` adds one scaled source Tachi cannon on a new
mounting collar. Its contact is obtained by ray intersection with the opaque
painted forward hull, and its mounting normal is taken from that source
triangle. It does not mount on the cockpit or duplicate an original gun.
`build_razorback_weapon.py` binds a single native cannon with single-turret
firing thresholds and a lower rate of fire. The catalog equips that cannon
as the primary weapon and a propulsion boost as the secondary system.

All rig files and renders under `obj/expanse-authoring` are review evidence,
not claims of completed gameplay validation. Remaining ships, source nozzle
placement, firing behavior and final installers require the same review.

## Native ship-selector portraits

`tools/build_expanse_portraits.ps1` renders each current review scene into
`obj/expanse-authoring/portraits/<ship GUID>/`. The selector's native
`DataStore.js` resolves `images/ships/<GUID>/main.png`; drafting also requests
`large.png`, and mastery views request bronze, silver or gold. Preserve the
vanilla dimensions: 464x207 main/store, 1631x652 large, and 278x124 mastery.
The portraits use transparent backgrounds, consistent studio lighting and a
horizontal three-quarter view of the actual adapted model. Framing is computed
from the visible vertices, including the source weapon assemblies.

`tests/test_expanse_portraits.py` checks all 42 images, dimensions, transparency,
framing and unclipped silhouettes. Packaging adds each image as a mandatory loose
UI resource, and both installers embed the full manifest. Unreal PAK inclusion
alone does not make loose Coherent UI image paths available to the selector.

## Current local test configuration

Rocinante now has six source PDC mounts and two dorsal/ventral launch positions
derived from the original fore-body hatch geometry, reviewed against the
production turnaround. The small chemical-thruster recesses at the bow are not
used as missile tubes. The original hatch leaves are posed open and the bays
have new dark launch sleeves. This is a static launch-ready configuration;
there is no firing-synchronised bay-door animation. Native static launch parts
retain the outward launch direction while guided explosive projectiles acquire
their targets. Unused inherited missile/utility positions are removed.

Avalanche and Mayotte use their verified source cannon/railgun groups. This
test build does not equip inherited torpedoes at unverified locations on those
two models. Their catalog descriptions match the implemented weapons.
The unarmed yacht's inherited weapon collections are cleared.

`tools/verify_expanse_assets.py` checks the actual cooked hull/armour bounds,
six armour regions, all twelve distinct gun meshes' native muzzle sockets,
weapon-group firing limits, mount counts and engine counts. The current check
passed for all seven ships. Required hangar shader references were also found
in all 573 cooked materials before packaging. These are authoring/loading
checks. Live aiming, firing, damage, performance and balance remain explicit
playtests; do not describe those behaviors as measured or validated yet.

## Texture, aiming and effect corrections

Source UVs use a top-origin V coordinate. The shared importer flips V once for
both hulls and articulated weapon pieces. Native muzzle sockets have identity
rotation relative to the barrel's +X axis; an imported -90 degree yaw made
shots leave sideways. Verification checks the cooked socket rotation as well
as its location. Surface guns allow five degrees of depression to reach the
forward aim line, with restricted fore arcs where the hull would obstruct fire.
The native subsystem selects eligible turrets, with Rocinante allowed to cycle
even when only one PDC can bear on the target.

`build_expanse_effects.py` gives each ship its own native effects system and
part. It removes vanilla shell/vernier meshes, which otherwise keep emitting
at the old hull's positions. Damage fire/smoke retains native activation but
uses localized spawn volumes at six measured imported-hull intersections.
Main-drive effects remain mapped separately to the source nozzle count.

The `expanse` branch includes `mods/expanse/payload`, including the cooked PAK
stored as five hash-checked binary parts, mandatory portraits, notices and the
account catalog. Git LFS is not required. After cloning, run
`powershell -ExecutionPolicy Bypass -File build.ps1 -LocalFleet` (Python 3 is
required to restore the PAK). The Windows and Linux build scripts automatically
reassemble the parts and verify their hashes. A fresh clone can build the installers from that bundle
without installing the authoring tools. When updating assets, regenerate and
test the bundle before replacing its tracked payload. Refresh the parts with
`python tools/restore_expanse_payload.py --split obj/expanse-authoring/FSO_Expanse_Experimental_P.pak`
and copy the new manifest, catalog, portraits and notices into the payload
directory together. Do not commit local
decryption keys, extracted game packages, editor binaries or runtime logs.
