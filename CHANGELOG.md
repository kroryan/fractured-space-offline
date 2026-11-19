# Changelog

## 1.1.0 — Co-op preview

- Added a Windows launcher mode screen for solo, hosting and joining, with the last selection remembered.
- Added local interface selection, prioritizing adapters whose names identify Tailscale, ZeroTier, Hamachi or Radmin.
- Added Windows launch progress and Linux desktop mode selection/progress dialogs.
- Added host join approval over TCP 8090, saved guest identities, and an approved-peer UDP 7777 relay.
- Added a dedicated-server wrapper that preserves the original `spserver.exe`; included it in the Windows installer and AppImage payload.
- Added the co-op Conquest game mode to the host wrapper; a headless server smoke test confirms the mode loads, enters `InProgress` and listens on UDP 7777.
- Added identity rewriting to the local Fireline response emulator and documented VPN/port setup.

### Known limitations

- The co-op path is an experimental preview and has not been validated with two live game clients.
- Automatic team placement and bot rebalancing are not confirmed; the game server behavior is undocumented.
- Internet play is best-effort and depends on the host network/VPN allowing TCP 8090 and UDP 7777.
