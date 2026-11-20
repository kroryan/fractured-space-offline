# The Expanse fleet integration plan

Status: planned work, not implemented gameplay. Unreal Engine 4.19.2 installation is in progress on the user's machine. Installing the editor is a prerequisite; it does not establish that new Fractured Space ship classes can already be authored or registered.

## Fleet identity and ownership

Include all distinct ship definitions from the seven reviewed packages. The current inventory is seven definitions and seven meshes; material groups, multiple textures and mesh subparts are not additional ships. Preserve the source names and credits in the source manifest.

The Tachi model's in-game display name will be **Rocinante**. Use the same source geometry, materials and textures as requested, retaining Tachi markings where present. This is a display-name change, not a newly modeled late-series variant. Do not create a duplicate Tachi roster entry. Keep the original model attribution and record the display-name adaptation in the asset notices.

Each ship that passes integration must have its own client/server identity, roster entry, loadout and default-account ownership. Preserve the existing fleet and level 68. Apply ownership to both fresh and existing local profiles. Never add an inventory license for a ship whose game assets or registration are absent.

## Intended roles and weapons

These are gameplay design targets, not final statistics or claims that every listed system exists in the source mesh. Confirm mount locations against geometry and verify armament references before implementation. Distinguish canon equipment from any gameplay adaptation in the ship descriptions.

| In-game name | Intended Fractured Space role | Weapon plan | Main tradeoffs |
| --- | --- | --- | --- |
| Rocinante | Mobile corvette / close escort | PDC-style projectile weapons and guided torpedoes. Preserve the Tachi model; do not assume the later Rocinante railgun exists on it. | Strong maneuverability and burst opportunities; light hull and limited sustained damage at range. |
| MCRN Avalanche | Light torpedo destroyer / flanker | Torpedoes as the main anti-ship threat, with a limited PDC battery after mount verification. | Faster repositioning and smaller silhouette; less durability, ammunition pressure and weaker sustained fire than capital ships. |
| UNN Mayotte | Heavy battleship / artillery | Railgun-style primary fire, torpedoes and defensive PDCs, subject to model and source verification. | Strong ranged pressure and hull; slow turns, restricted firing arcs and vulnerability to flanking. |
| MCRN Donnager | Capital battleship / fleet anchor | Heavy railgun-style battery, torpedoes and PDC coverage, subject to mount verification. | High durability and area pressure; large target, slow handling, clear reload windows and limited pursuit ability. |
| MCRN Chariot-Type Dropship | Shuttle / boarding-support role | Verify the modeled/canon armament first; no invented heavy battery. Use game-supported utility actions for support rather than claiming a new marine boarding simulation. | Small and agile, low durability and combat output; utility should justify its place in a team. |
| Razorback | Civilian racing pinnace / reconnaissance | Unarmed base configuration. Sensor and objective utility are gameplay adaptations, not claims of canon weapons. | Very fast, extremely fragile; contributes information and positioning rather than heavy damage. |
| Epstein's Yacht | Civilian experimental craft / exploration-support | Unarmed base configuration, pending license clearance. A controlled propulsion burst may represent its experimental drive. | Low durability, limited combat contribution and restricted burst duration; no permanent acceleration or invulnerability. |

The civilian craft must not be advertised as equivalent combat dueling ships. If the game cannot support a useful noncombat role without undermining the match, retain ownership and access for suitable sandbox/scenario use and document mode restrictions instead of adding fictional weapons.

## Balance method

1. Measure existing Fractured Space ships at the same upgrade level before choosing numeric values. Select a comparison ship for each military role and use its match contribution as a baseline; do not multiply health or damage directly by the SpaceEngine length or mass.
2. Tune hull durability, speed, acceleration, turn rate, hitbox, damage, range, firing arcs, reload and utility together. Larger ships receive explicit mobility and exposure costs. Small ships must remain hittable and readable.
3. For PDCs, reuse compatible projectile behavior first. Do not claim automatic missile interception unless target acquisition and server-side interception actually work. For torpedoes, verify guidance, tracking limits, collision, friendly-fire rules and counterplay. For railguns, verify authoritative hit registration and visible reload feedback.
4. Reuse compatible stock damage, defenses and ability mechanics initially. Avoid silently introducing an incompatible shield/armor system merely to imitate the source fiction.
5. Compare time to destroy, sustained damage and burst damage at close/medium/long range; then test turns, firing arcs, projectile travel, hitbox behavior and objective utility against stock counterparts. Evaluate team contribution, not only stationary damage output.
6. Adjust after solo and co-op play sessions. Numeric values remain provisional until these checks are complete; no measured balance results exist yet.

## Meshes, effects and animation

The inspected packages contain SpaceEngine SM02 geometry, ship/material scripts, textures and some audio. No Unreal animation assets or animation sequences were found. Do not treat a static mesh as an animated skeletal asset.

- Preserve the requested source models. Validate orientation, units, normals, UVs and material assignments before cooking. Build LODs and collision appropriate for gameplay; capital-ship meshes need particular performance review.
- Reuse compatible Fractured Space thruster particles, firing flashes, projectile/impact effects, trails and explosion effects by reference where possible. Do not redistribute television-derived audio; reference game audio or separately cleared replacements.
- Inspect turrets for separable components. If articulation is needed, author pivots/attachments or a minimal rig, then implement aiming and recoil. Do not rotate a whole hull section because the source lacks a turret bone.
- Add missile launch points and firing sockets matching visible hardware. Verify that effects, muzzle positions, firing arcs and collision agree on both client and server.
- Reuse existing effects/animations only after checking asset dependencies and compatibility. Any new turret movement, recoil or deployment animation must be authored and tested; none is assumed to be included in these SpaceEngine packages.

## Implementation sequence and acceptance gates

1. **Toolchain and rights:** confirm the installed 4.19.2 editor/cooker, establish a reproducible asset-authoring project, and resolve the yacht license discrepancy. Maintain separate licenses and notices for graphics; the project code remains GPL-3.0.
2. **First complete ship:** convert Rocinante's source mesh/materials, author collision and attachments, and establish compatible game class/roster registration. Confirm that it loads as an additional ship without replacing a stock ship. If native game classes or registries require unavailable dependencies, investigate that blocker before converting the remaining fleet.
3. **Gameplay and inventory:** add loadout/weapon definitions and local ownership. Verify fresh-profile ownership, existing-profile migration, hangar display/selection, player spawn, bot spawn, server loading and a completed match.
4. **Remaining fleet:** apply the proven pipeline to every distinct source definition, preserving each license, role and model identity. Keep the yacht deferred until its rights are resolved.
5. **Balance and presentation:** complete LODs, material review, attachments, effects and required animation; perform role-based balance checks and solo/co-op validation.
6. **Installer and release:** include only validated cooked assets in both platform manifests with hashes, backups/restoration and notices. End users must receive the ships through the normal installer/AppImage with no editor or conversion steps. Publish built binaries, checksums and an accurate stable-release changelog after these gates pass.

## Source references

- Package attribution, license evidence and conversion prerequisites: [source review](README.md) and [source manifest](source-manifest.json).
- [Rocinante TV reference](https://expanse.fandom.com/wiki/Rocinante_(TV)) distinguishes the original Tachi armament from the later railgun addition. This is a secondary lore reference; verify exact hardware against the model and authoritative material before finalizing hardpoints.
- SpaceEngine scheme lengths and physics values are source metadata, not Fractured Space balance values.
