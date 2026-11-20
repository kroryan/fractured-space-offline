# Project rules

## Keep upstream projects in sync

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
