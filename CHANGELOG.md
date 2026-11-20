# Changelog

## Unreleased — Server-fix reference review

- Reviewed `Makichika/Fractured-space-fixe-` at `7e43fb70ca660c35ae903fcc1f703b9c0a624cb0` and recorded it in `rules.md` as a reference project.
- Deferred its advertised server-side fixes because the repository supplies client files and says the server changes are installed on the author's servers; it contains no distributable server implementation to port.
- Did not import its game executable, Bootstrapper files or event PAKs: the executable differs from this project's patched binary, and the event content requires compatible server support.

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
