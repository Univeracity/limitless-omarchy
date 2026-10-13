# Complete adapter wheel contents and source

The existing `0.2.1` adapter wheel has SHA-256
`0a9b19cab1a9de865da8e24b94beb7aabc92b80eb35b5ab34f65269c27470380`.
Its complete inventory contains 19 files: 12 Python package files, two license
files, and five generated distribution metadata files. The inventory covers
every archive member, including files outside the Python package prefix.

The historical source is public at
[`c2e303ba63024ee4e1c4cbc595488fa9dfef7170`](https://github.com/Univeracity/limitless-omarchy/tree/c2e303ba63024ee4e1c4cbc595488fa9dfef7170).
The [inventory recipe](releases/0.2.1-wheel-inventory.json) and
[public workflow](../.github/workflows/wheel-inventory.yml) bind the exact
released wheel to that source tree:

- Every package file and license must match its source bytes exactly.
- The declared `setuptools.build_meta` backend at version `83.0.0` regenerates
  `METADATA`, `entry_points.txt`, and `top_level.txt` from a fresh source archive.
  Each complete file must match exactly, including all metadata headers,
  dependency declarations, the embedded README, and the console entry point.
- `WHEEL` must declare wheel format 1.0, the pinned setuptools generator,
  pure-Python installation, and the `py3-none-any` tag. No unexpected installer
  scheme or additional member is accepted.
- `RECORD` must inventory every member exactly once and bind every other file's
  SHA-256 and byte length. Only its own entry has an empty hash and size.
- The release download must match both the declared digest and the wheel
  already committed in the historical runtime bundle.

The report includes the source commit and tree, source input digests, every
member's digest, size, installation scheme and source/generation mapping, and
the public workflow identity. On `main`, a separate job authenticates that
report as a signed predicate for the original wheel digest and verifies it.

This is newly generated contents/source evidence. No wheel is rebuilt or
replaced, and it does not claim an attestation from the original release build
or a security audit. The tooling commit is separately identified from the
historical package source. Existing runtime and marketplace snapshots remain
unchanged.

## Verify the evidence

Download the wheel from the
[`v0.2.1` release](https://github.com/Univeracity/limitless-omarchy/releases/tag/v0.2.1).
Using a current GitHub CLI:

```sh
gh attestation verify limitless_omarchy-0.2.1-py3-none-any.whl \
  --repo Univeracity/limitless-omarchy \
  --signer-workflow Univeracity/limitless-omarchy/.github/workflows/wheel-inventory.yml \
  --predicate-type https://github.com/Univeracity/limitless-omarchy/releases/wheel-inventory/v1 \
  --format json
```

Inspect the verified predicate's historical source commit, wheel digest and all
19 file mappings. Successful main runs retain the unchanged wheel, JSON report,
Sigstore bundle and verification output in `authenticated-adapter-wheel-inventory`.
A downloaded Sigstore bundle can also be verified with `--bundle`.

## Generate the mapping locally

Use Python 3.11 or newer with `setuptools==83.0.0`, a checkout containing the
historical Git commit, and the original release wheel:

```sh
python scripts/inventory-release-wheel.py \
  --source-root /path/to/source-checkout \
  --recipe docs/releases/0.2.1-wheel-inventory.json \
  --wheel /path/to/limitless_omarchy-0.2.1-py3-none-any.whl \
  --output /path/to/inventory-output
```

Local correspondence checks alone do not authenticate the public report; verify
the workflow signature separately. The original runtime-bundle verifier checks
package Python files, whereas this separate evidence gate checks the complete
released adapter wheel and generated installation metadata.
