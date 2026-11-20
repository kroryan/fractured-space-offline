FRACTURED SPACE BOOTSTRAPPER OFFLINE
====================================
https://github.com/kroryan/fractured-space-offline

How to play
-----------
Open "Fractured Space Bootstrapper Offline" (Start menu, desktop or search).
- Starts a built-in local server (Fireline emulator) on http://127.0.0.1:8080
- Launches the game against it (no Discord, no internet), in windowed
  fullscreen at your screen resolution
- When you close the game, the launcher exits too

To play against bots: Play -> Training -> Solo vs AI.

To host co-op, select the host mode and choose the total number of human players
and how many humans should be on your team. Approved guests are assigned to the
remaining team slots. Guests select Join and enter the host's VPN or LAN address.

Limitations
-----------
- The account is a recorded one from the official servers (not your online progress).
- Progress is NOT saved: the local server always answers the same.
- Store, purchases and official online matchmaking do not work.
- Co-op uses the local dedicated-server wrapper and requires TCP 8090 and UDP
  7777 between players. Team assignment is sent with the Unreal join URL; the
  game may override it and has not been validated with two live clients.
- To play on the community online servers use the Fractured Space Bootstrapper.

Files
-----
FracturedSpaceBootstrapperOffline.exe  launcher + local server
responses.json                         recorded official server responses
gamepath.txt                           game folder chosen in the installer
requests.log                           requests made by the game (useful if something fails)
uninstall.exe                          uninstaller (also in Settings > Apps)

