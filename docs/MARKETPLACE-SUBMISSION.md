# Omarchy marketplace submission and verification

This file prepares the repository for omarchyplugins.com. It does not submit
the plugin, make the repository public, create a release, or claim a security
certification.

Authoritative process references:

- [Marketplace submission guide](https://github.com/HANCORE-linux/omarchy-plugin-marketplace/blob/main/SUBMISSION.md)
- [Marketplace verification definition](https://github.com/HANCORE-linux/omarchy-plugin-marketplace/blob/main/VERIFICATION.md)
- [Marketplace security baseline](https://github.com/HANCORE-linux/omarchy-plugin-marketplace/blob/main/SECURITY.md)
- [Official Omarchy shell-plugin guide](https://github.com/basecamp/omarchy/blob/quattro/manual/32-shell-plugins.md)

## Listing metadata

- Repository: `https://github.com/Univeracity/limitless-omarchy`
- Plugin ID: `univeracity.limitless-library`
- Category: `Productivity`
- Tags: `AI`, `Quickshell`, `Security`
- License: Apache-2.0

The ID was absent from the marketplace registry when checked on 2026-08-22.
It is the permanent marketplace identity and should not change after listing.

## Maintainer notes

Use this text in the submission's **Maintainer notes** field:

> Limitless Library is a panel plus bar widget. Omarchy's ordinary Git add,
> validation, review, and enable flow runs no plugin install hook. After the
> plugin is enabled, the user may click **Install local runtime**. That explicit
> action creates a virtual environment only under
> `XDG_DATA_HOME/limitless-omarchy/runtime` and runs Python's package installer
> there for this reviewed checkout and the public Limitless Library dependency
> pinned to a full Git commit. It requires no elevated access, does not modify
> the system Python, and can be skipped; the action is why the marketplace
> baseline reports the `package-manager` review capability. The current
> baseline reports no findings and no other review capability. Managed service
> access, publication, exact-component installation, and enablement are
> separate explicit user actions. A build with no official service locator
> remains local-only.

## Exact baseline result

Against marketplace commit
`aa6d4be1b21ccb57cacd5f67d3ffd1f765c97237` on 2026-08-22, the repository's
local exact-source preflight produced:

```text
outcome: review-required
blocking findings: none
review capabilities: package-manager
```

The evidence consists of the optional CLI installation examples in the root
README and the two package-installer calls in
`scripts/limitless-omarchy-runtime`. Both runtime calls target the isolated
panel-owned virtual environment. The preflight is enforced in CI by
`scripts/verify-marketplace-baseline.mjs` against the pinned marketplace
scanner source.

This result is intentionally not rewritten into an automatic `passed` result.
Removing the UI-owned setup would make first use worse and would hide the real
capability from reviewers. The marketplace's selective policy permits an
authorized maintainer to accept this exact capability and publish the exact
commit as Verified.

## External dependencies and effects

| Dependency or effect | Boundary |
| --- | --- |
| Omarchy Quattro and its Quickshell modules | Host plugin runtime; native `omarchy plugin validate` is run in CI. |
| Python 3.11+ with virtual-environment support | Required only after the user selects **Install local runtime** or directly chooses the optional CLI. |
| Limitless Library | Public Git dependency pinned to a full 40-character commit in `pyproject.toml`. |
| Initial network use | Omarchy clones this repository; the explicit runtime setup may fetch the pinned dependency and Python dependencies. |
| Optional managed network use | Begins only after **Enable official service** verifies release-pinned trust and the user later chooses a service action. |
| Local data | Runtime under the configured XDG data directory; owner-selected catalogs and owner-only state remain local unless separately published. |
| Privilege | No `sudo`, `pkexec`, system-Python modification, service unit, sudoers policy, or passwordless privilege path. |
| Desktop mutation | A query never changes the desktop. Reviewed exact-component installation and enablement are separate actions and use Omarchy's native lifecycle. |

## Public cutover checklist

1. Freeze a clean release commit after CI, current Omarchy validation, a real
   Omarchy/Hyprland visual smoke, and a fresh current-marketplace baseline.
2. Confirm the repository root contains `manifest.json`, `README.md`,
   `LICENSE`, installation and removal directions, and the owned root preview.
3. Make `Univeracity/limitless-omarchy` public and confirm it is active and
   unarchived. Marketplace validation refuses private repositories.
4. Record the full 40-character public `main` SHA. Do not push another commit
   while the submission is being reviewed unless the submission is deliberately
   rerun against the new SHA.
5. Open the marketplace's **Submit a plugin** issue with the repository,
   category, tags, notes above, and all five owner-confirmed checklist items.
6. Review the bot's compatibility and static-baseline reports. The expected
   disposition is `review-required`, with no findings and only
   `package-manager`.
7. Ask a write-authorized marketplace maintainer to review that exact evidence
   and apply `approved-and-verified`. The label event and fresh rescan must bind
   the same repository, plugin ID, commit, policy version, findings, and
   capabilities.
8. Confirm the published card says **Verified** and resolves the intended
   exact commit. A later upstream commit correctly changes the public state to
   **Update unverified** until the marketplace update workflow qualifies it.

Marketplace verification is an exact-snapshot static-baseline status. It is
not a security audit, warranty, certification, or endorsement, and Omarchy
plugins remain unsandboxed code that users should review before enabling.
