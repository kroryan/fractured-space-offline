# Project rules

## Keep upstream projects in sync

This project incorporates work from these upstream repositories:

- `https://github.com/Tigerhacker/refireline` — Fireline emulator and recorded-response foundation.
- `https://github.com/Tigerhacker/fractured-bootstrapper` — origin of the Fractured Space client patch.

When either upstream repository changes, review its new commits and compare the affected files with this project. Integrate compatible fixes and improvements into this project as soon as practical. Preserve the offline launcher, local response data, identity rewriting, co-op behavior, and other project-specific changes while doing so; do not overwrite those changes with a blind copy.

For each integration, check that the change applies to the versions and file formats used here, resolve conflicts deliberately, and run the relevant build or smoke checks. If a change cannot be integrated safely, record the upstream commit and the reason it was deferred in the changelog or a follow-up issue. Keep attribution and the upstream license notices with imported code and assets.

## Co-op team allocation

The host controls co-op lobby settings. Any team-allocation UI or behavior must make the human-player distribution explicit for the expected party size and must be passed to the game server in a way that is verified to affect actual player teams. Do not present a requested split as supported when only the game's automatic placement is available. Keep documented limitations accurate until assignment is confirmed with live clients.
