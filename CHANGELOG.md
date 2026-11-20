# Changelog

## Unreleased — The Expanse source audit

- Expanded the current inventory to seven ships with the Chariot-Type Dropship, and added a proposed integration/balance plan. The Tachi asset is planned to appear as Rocinante with its source model unchanged.

- Inventoried all six downloaded SpaceEngine packages, including archived definitions: one ship and one SM02 mesh per package, with source paths, sizes and SHA-256 hashes.
- Added model/texture and SpaceEngine adaptation credits to README.md, linked the declared per-asset licenses, and recorded the yacht's conflicting license notices.
- Added a repeatable source audit script. Playable integration and default-account ownership remain pending compatible Unreal 4.19.2 assets and client/server registration; no new ship assets or installer binaries are published by this audit.

## 1.4.1 — English-only interfaces and documentation

- Removed automatic Spanish localization and translated strings from the installer, launcher and DirectX 11 F1 menu. All application-owned text now uses English regardless of the Windows display language.
- Translated the trainer security documentation into English and recorded the English-only policy in project rules.
- Rebuilt the Windows installer and Linux AppImage. This release retains the personal profiles and F1 trainer features from 1.4.0, including its documented gameplay verification limits.

## 1.4.0 — Personal profiles and in-game F1 menu

- Adapted the Dreadnought launcher dark palette and DirectX 11 F1 overlay to Fractured Space.
- Embedded the Makichika solo trainer engine behind an authenticated loopback bridge, with player/allied/enemy invulnerability and allied/enemy ship spawning exposed inside the game. The trainer uses the configured original server path and retains upstream signature checks. Guests cannot operate the host trainer.
- Added profile controls for credits, level 68 and resetting personal statistics. The default inventory keeps all ships unlocked.
- Removed inherited combat history from new Windows and Linux profiles, including account, mode, ship and combo statistics. Added per-identity persistence for supported PUT/PATCH updates and live result event recording, with match-ID duplicate protection, without changing recorded inventory/experience.
- Added trainer revision/hashes and update rules, and retained overlay third-party licenses.

### Verification limits

- Profile reset, persistence and identity isolation were verified locally. The trainer and overlay compile; runtime trainer tests were blocked by automatic tool review, so combat actions and F1 rendering in the actual game remain unverified.
- Live engine result events are recorded locally and imported into the personal profile. Aggregation and duplicate protection were tested with representative events; real match completion still needs gameplay validation. Only explicitly reported statistics are accumulated.
- The native in-game F1 overlay is currently Windows-only; the AppImage includes the personal statistics backend.

## 1.3.0 — Community client fixes

- Bundled all 14 game-side files from Makichika/Fractured-space-fixe- at `7e43fb70ca660c35ae903fcc1f703b9c0a624cb0` in the Windows installer and Linux AppImage, with SHA-256 verification.
- Updated the patched client executable, draft UI, scoreboard/player scripts, map jamming, Venturer skins and Protector shield visuals; included Charon and Christmas event client content and Discord avatar client support.
- Preserved the offline launcher, local backend, co-op wrapper and existing offline UI patches.
- Added a reproducible update script and revision/hash lock for future imports. Bootstrapper application files are not installed over the user's online Bootstrapper.

### Compatibility limits

- Charon/Christmas modes and game-time effect clocks require compatible server behavior. Client content alone does not add the reference author's private server fixes.
- Discord profile avatars require the reference Bootstrapper's local avatar service; offline play retains the client's fallback avatars.
- Automated checks cover packaging, backend identity, co-op admission and server startup. Full visual gameplay and two-live-client team assignment require a play session.

## 1.2.0 — Co-op team distribution

- Added host controls for two to four human players and the number of humans on the host's team, covering all requested splits including 1–1, 1–2, 2–1, 1–3, 2–2 and 3–1.
- Added per-guest team assignment during host approval, persistent guest team identities, and capacity enforcement in the Windows launcher and Linux AppImage.
- Passed each assigned team through the dedicated-server wrapper as a `Team` Unreal URL option and included the selected team sizes in the host map URL.
- Isolated offline installation state from the online Bootstrapper marker; the installer now stops instead of replacing a different Bootstrapper patch in the shared game folder.
- Updated the launcher and wrapper version to 1.2.0.

### Verification limits

- Team sizes, admission assignments and wrapper URL options are covered by local smoke checks; the game server may override requested teams and still needs a two-live-client confirmation.
- Bot balancing remains controlled by the game's undocumented server behavior.

## 1.1.0 — Co-op preview

- Added a Windows launcher mode screen for solo, hosting and joining, with the last selection remembered.
- Added local interface selection, prioritizing adapters whose names identify Tailscale, ZeroTier, Hamachi or Radmin.
- Added Windows launch progress and Linux desktop mode selection/progress dialogs.
- Added host join approval over TCP 8090, saved guest identities, and an approved-peer UDP 7777 relay.
- Added a dedicated-server wrapper that preserves the original `spserver.exe`; included it in the Windows installer and AppImage payload.
- Added the co-op Conquest game mode to the host wrapper; a headless server smoke test confirms the mode loads, enters `InProgress` and listens on UDP 7777.
- Added identity rewriting to the local Fireline response emulator and documented VPN/port setup.
- Rewrites player identity claims in the recorded access token and compressed refresh token in both launchers.

### Known limitations

- The co-op path is an experimental preview and has not been validated with two live game clients.
- Automatic team placement and bot rebalancing are not confirmed; the game server behavior is undocumented.
- Internet play is best-effort and depends on the host network/VPN allowing TCP 8090 and UDP 7777.
