# Project rules

## Keep upstream projects in sync

`main` is the normal offline product. The user has parked `expanse` as a secondary development branch. Do not merge its fleet, catalog or mandatory ship assets into `main`. Main installers must disable any leftover Expanse test PAK when switching back; retain a recovery copy and preserve player profiles. Publishing normal stable releases does not authorize an Expanse release.

This project incorporates work from these upstream repositories:

- `https://github.com/Tigerhacker/refireline` — Fireline emulator and recorded-response foundation.
- `https://github.com/Tigerhacker/fractured-bootstrapper` — origin of the Fractured Space client patch.

When either upstream repository changes, review its new commits and compare the affected files with this project. Integrate compatible fixes and improvements into this project as soon as practical. Preserve the offline launcher, local response data, identity rewriting, co-op behavior, and other project-specific changes while doing so; do not overwrite those changes with a blind copy.

For each integration, check that the change applies to the versions and file formats used here, resolve conflicts deliberately, and run the relevant build or smoke checks. If a change cannot be integrated safely, record the upstream commit and the reason it was deferred in the changelog or a follow-up issue. Keep attribution and the upstream license notices with imported code and assets.

## External server-fix reference

- `https://github.com/Makichika/Fractured-space-fixe-` is a reference for Fractured Space client fixes and server behavior, not a source dependency or an upstream of this project.
- Review its client scripts, executable and PAK updates individually. Do not copy its Bootstrapper directory. Review the game executable for offline backend support before updating it; preserve our offline launcher integration.
- Its README says the listed server fixes are installed on the author's servers. Treat those server-side behavior descriptions as reference requirements only unless distributable server source or a reproducible patch becomes available. Do not claim those fixes are integrated based only on the README or client files.
- Event PAKs that require a compatible server are not sufficient to enable those events on this project's local server. Verify both client and server behavior before adding them.

## Co-op team allocation

The host controls co-op lobby settings. Any team-allocation UI or behavior must make the human-player distribution explicit for the expected party size and must be passed to the game server in a way that is verified to affect actual player teams. Do not present a requested split as supported when only the game's automatic placement is available. Keep documented limitations accurate until assignment is confirmed with live clients.

## Updating Makichika client fixes

The reviewed revision and exact imported bytes are recorded in `tools/makichika-lock.json`. The installed payload is self contained; end users never need to download the reference repository.

1. Clone the reference into ignored `obj/reference-server` if absent; otherwise run `git -C obj/reference-server fetch origin` and check out the intended commit.
2. Compare `git log` and `git diff` against the revision in the lock, including executable changes and server dependencies.
3. Run `python tools/sync_makichika.py --source obj/reference-server` to list changed files and hashes without modifying the project.
4. After reviewing compatibility, add `--apply` to copy the game-side payload and update Windows/Linux manifests and the lock together. Inspect removals or renamed files manually; the tool deliberately preserves offline resources.
5. Review the resulting diff, check local Fireline support, build both binaries and run relevant smoke checks. Bump the patch level/version and update the changelog for a release. Document server-dependent functionality accurately.

The import covers the `Space` payload. Bootstrapper application binaries belong to a different launcher; implement any needed service in our own launcher before claiming equivalent online integration.

## Updating Tigerhacker Bootstrapper

Use `tools/bootstrapper-lock.json` and `docs/bootstrapper-updates.md` as the review baseline. Compare both new source commits and published release assets: v2.0.1's published package includes changes absent from its tagged source manifest. Validate the release ZIP against its SHA256SUMS before importing with `tools/sync_bootstrapper.py`. Preserve offline statistics hooks and server ordering. Import only the reviewed license/bundle routes with `tools/sync_bootstrapper_entitlements.py`; never replace local progression/statistics or player identity behavior with captured history. Review changes to that route inventory before applying the script.

Retire overlay PAKs when their assets are incorporated upstream, including removal from both installer manifests and recovery-safe retirement in existing installs. Never copy the online Bootstrapper application directory or import Discord authentication, avatar services or Electron updater requirements into the offline launcher. Keep the published-client hashes, platform manifests, notices and changelog in sync; build Windows/Linux and run payload, profile, UI and relevant native loading checks before a stable release.

## Dreadnought launcher and Fractured Space trainer reference

- `C:\Users\PC\dreadnought-offline` supplies the dark launcher palette and DirectX 11 F1 overlay design. This project owns its adapted launcher and backend; keep the third-party ImGui, kiero and MinHook notices in `src/Overlay/third_party`.
- `https://github.com/Makichika/Fractured-space-cheat-menu` supplies the local-server trainer engine. The reviewed revision and original hashes are in `tools/trainer-lock.json`. Keep `src/Trainer/README.md` and `SECURITY.md` for provenance.
- For updates, fetch the reference into ignored `obj/reference-cheat-menu`, compare its revision and hashes against the lock, and merge changes into `src/Trainer` individually. Preserve the authenticated headless bridge, configured server-path filtering, process lifecycle and upstream executable signature guards. Never restore the separate trainer window as the normal user flow.
- The F1 menu must render in the game's own DirectX 11 frame. Guests cannot issue server-memory actions; only the local host can operate its server. Never target the wrapper executable or select an arbitrary server by PID.
- Keep personal statistics separate from recorded account unlocks and experience. New profiles start with zero historical combat statistics and preserve the unlocked ships and level 68. Persist supported updates per player identity and test isolation/reset across restarts. Do not claim match result recording unless an actual match reports its results through a supported endpoint.

## English-only language policy

All project-owned interfaces, messages, trainer/F1 controls, documentation, release titles and changelogs must be written in English. Do not select another language from the operating system locale or reintroduce translated UI strings when importing reference updates. Keep Fractured Space launched with its English culture setting. Preserve third-party license notices and identifiers unchanged.

## Imported ships and default ownership

Inventory all loose and archived ship definitions in imported packages; do not infer ship count from package count. `tools/audit_expanse.py` and `mods/expanse/source-manifest.json` record the current seven-package review. Resolve each asset's license separately, preserve credits and modification notices, and exclude unlicensed show-derived audio. Keep non-GPL graphics under their own applicable licenses.

Every successfully integrated playable ship must be owned by the default local account, alongside the existing fleet. Add ownership only after compatible cooked assets and client/server definitions exist and the ship can actually load; source-only SpaceEngine meshes or fictional inventory entries are not integration. Check hangar selection, spawning and gameplay before publishing a release claiming the ships are included.
