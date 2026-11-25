# Bootstrapper 2.0.1 offline integration

The reviewed source is `Tigerhacker/fractured-bootstrapper` at
`db67933003c5dd453edd9d46ed20758c595affa4`. The authoritative published payload
is release **v2.0.1**, published 2026-11-25, patch level **34**. Its ZIP and
Debian package contain newer files than the tag's source manifest (which still
says patch level 33 and labels five patches testing). Those five fixes are
explicitly listed in the published release notes. `tools/bootstrapper-lock.json`
records the exact published ZIP digest and each imported file digest; this
project uses patch level **35** to distinguish its offline adaptations.

| Area | Integration |
| --- | --- |
| Client executable | Published executable, including null Steam lobby guard, dead-missile warning filtering and drafting cache refresh. |
| BP.pak | Published HUD/automation fixes, minimap jamming, Protector shield field and Venturer skin bindings. |
| Game mode UI | Published Frontline panel, Solo/Legacy layouts, translations and styles. |
| Entitlements | Only the two license responses (1,237 licenses each) and bundle check (697 licenses) from the published package. Existing identity rewriting remains. |
| Local launch state | Free loopback port, random per-process nonce and CORS-enabled launch check. A stale flag cannot identify an active offline session. |
| Network configuration | Published BaseEngine.ini, including ConfiguredInternetSpeed=200000 and ConfiguredLanSpeed=800000. This does not claim server throughput or Last Stand stability was measured. |
| Linux | Declared Steam Linux Runtime, Flatpak Steam HOME fallback, AppImage environment cleanup, waitforexitandrun, case-insensitive lookup and retained launch output. |
| Preserved local behavior | Offline result recording in results-script.js, server ordering in startgame-script.js, account identity rewriting, personal statistics, host/guest admission and F1 trainer. |
| Excluded online application features | Discord authentication, avatar HTTP service, Electron UI/auto-updater, online backend selection and online package distribution. |

`Makichika_MapJamming_P.pak`, `Makichika_ProtectorShield_P.pak` and
`Makichika_VenturerSkins_P.pak` are superseded by the published BP.pak. Both
platforms retire them with recovery copies so they cannot override newer
assets. The normal edition also retires a leftover Expanse test PAK. Profiles
and recorded player progress are preserved.

## Repeating the update

1. Fetch `obj/reference-bootstrapper` and compare commits, manifests, patch
   descriptions and published release notes against the lock. Do not infer
   that every testing patch ships, or that the tag's checked-in data is complete.
2. Download the published manual-patch ZIP. Run
   `python tools/sync_bootstrapper.py --zip <zip> --release <tag> --revision <sha>`
   to review; add `--apply` only after compatibility review. It verifies every
   ZIP entry against SHA256SUMS and updates both platform manifests. Review
   every preserved local adaptation against the corresponding new upstream file.
3. If entitlements changed, extract only `resources/data/fireline-responses.json`
   from the official package and review it. Run
   `python tools/sync_bootstrapper_entitlements.py --source <file> --apply`.
   Do not import captured statistics, crew XP or player progression.
4. Review retired overlays and update migration code alongside both manifests.
   Bump this project's version/patch level, changelog and notices. Build with
   `powershell -ExecutionPolicy Bypass -File build.ps1`.
5. Run the Python tests, `node tests/gamemodes-offline.test.js`, relevant C#
   smoke tests and `tests/Smoke-UpstreamRuntime.ps1`. The native test copies
   mutable files into an isolated workspace stage and never patches the game
   installation. Review failures before publishing.

Automated checks cover payload hashes, executable patch bytes, UI state,
entitlement routes, identity/profile isolation and Proton command construction.
They do not establish balance, every mode's end-to-end behavior or runtime
compatibility on every Linux distribution. Keep those limits explicit.
