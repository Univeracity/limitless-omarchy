# Reviewed runtime bundle

The Omarchy panel installs no mutable Git checkout and runs no package build.
It verifies this directory first, installs the complete dependency graph from
`requirements.lock` with hashes required and binary distributions only, then
installs the two reviewed local wheels without dependency resolution or index
access. Dependencies are reinstalled from hash-approved bytes during setup so
an older mutable runtime cannot be grandfathered into the reviewed release.

Successful setup stores an owner-only `installed-bundle.json` beneath the XDG
runtime root after both wheel installation and seed-catalog synchronization.
The launcher compares that receipt with the plugin's current bundle before
running an installed runtime. An older or unrecorded installation reports
`local-runtime-update-required`; the panel offers **Update local runtime**.
Updates keep owner settings and `local-*` catalog entries. A failed reinstall
removes the success receipt so the launcher cannot report the runtime current.
This receipt identifies the installed bundle; it is not a continuous integrity
scan of every runtime file.

`bundle.json` binds the lock and wheels to exact SHA-256 digests. The core
wheel is built from the public Limitless Library commit named in that manifest.
The plugin wheel is also checked byte-for-byte against the Python sources in
this release by `scripts/verify-runtime-bundle.py`.

## Maintainer regeneration

Regeneration is a release operation, not an end-user setup operation:

1. Compile `requirements.in` with Python 3.12 and `pip-tools==7.6.1`, using
   `--generate-hashes --strip-extras`.
2. Build both pure-Python wheels twice with `build==1.5.0`,
   `setuptools==83.0.0`, and `wheel==0.48.0`, setting the same
   `SOURCE_DATE_EPOCH`; require identical SHA-256 digests across both builds.
3. Replace the reviewed wheels and update their digests and provenance in
   `bundle.json`.
4. Run `python scripts/verify-runtime-bundle.py --root .` and the full test
   suite before publishing the commit.

The lock intentionally contains hashes for supported distributions across
platforms. A compatible hash-approved wheel may be fetched from the Python
package index during setup; arbitrary source distributions and future bytes
are rejected.
