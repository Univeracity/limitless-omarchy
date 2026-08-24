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

The ID was absent from the marketplace registry when checked on 2026-08-24.
It is the permanent marketplace identity and should not change after listing.

## Maintainer notes

Use this text in the submission's **Maintainer notes** field:

> Limitless Library is a panel plus bar widget. Omarchy's ordinary Git add,
> validation, review, and enable flow runs no plugin install hook. After the
> plugin is enabled, the user may click **Install local runtime**. That explicit
> action creates a virtual environment only under
> `XDG_DATA_HOME/limitless-omarchy/runtime`. Before changing it, a
> standard-library verifier checks the complete dependency lock and both
> shipped pure-Python wheels against SHA-256 digests in the reviewed release
> manifest. The installer accepts only hash-approved binary dependencies, then
> installs the local core and adapter wheels with no index, dependency
> resolution, Git checkout, or package build. The core wheel is tied to public
> Limitless Library commit `bbd8d312151e01503c85bce40ebbb3fa22aee66d`.
> Setup requires no elevated access, does not modify the system Python, and can
> be skipped; the action is why the marketplace baseline reports the
> `package-manager` review capability. Managed service
> access, exact-component installation, and enablement are separate explicit
> user actions. Method publication is local by default. It becomes automatic
> only after the user explicitly connects the official service, verifies its
> publication policy, chooses Public + Automatic, and saves that standing
> authorization. A build with no official service locator remains local-only.
>
> After that same explicit setup action, the panel may configure one named
> local MCP entry for the agent selected under Omarchy's own Default Agent
> setting. It uses the current agent client's verified MCP surface, verifies
> the exact local command/arguments, and keeps a local ownership descriptor.
> That one connection exposes standard general Limitless query, a concise
> Omarchy-specific query, and compact method registration; it does not limit the
> selected agent to Omarchy work.
> It never overwrites an existing entry of that name; unavailable or unsupported
> agents are reported locally without blocking the rest of setup.

## Exact baseline result

Against marketplace commit
`a9a1620b21065040ab4c0aba60289b08ab69cb99` on 2026-08-24, the repository's
local exact-source preflight produced:

```text
outcome: review-required
blocking findings: none
review capabilities: package-manager
```

The evidence consists of the development-only installation examples in the
root README and the two package-installer calls in
`scripts/limitless-omarchy-runtime`. Both runtime calls target the isolated
panel-owned virtual environment. Unlike the rejected 0.1.0 setup shape, this
release executes no build backend and performs no mutable dependency or Git
resolution: the full graph is exact and hash-required, source distributions
are refused, and the shipped wheels are digest-bound and verified before
installation. The preflight is enforced in CI by
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
| Limitless Library | Shipped pure-Python wheel tied to a full public commit and exact digest in `runtime/bundle.json`. |
| Initial network use | Omarchy clones this repository; explicit runtime setup may fetch only exact hash-approved binary dependencies. Core and adapter wheels are local and install with no index. |
| Optional managed network use | Begins only after the explicit **Connect to Limitless Library service** action verifies release-pinned trust and the user later chooses a service action. |
| Local data | Runtime, catalog, immutable method records, sharing projections, and owner-only state live under the configured XDG data/config roots. Local paths never enter source-free public material. |
| Optional contribution | Compact method registration is a local write. Public transfer occurs only under a saved, digest-bound Public policy; Automatic + Public is an explicit standing authorization and service failure remains retryable. |
| Agent configuration | The explicit setup or connection action may add one `limitless-omarchy` user-scoped local MCP server for the current Omarchy default and owner-selected additional agents. Only verified agent-client adapters are used; collisions and modified entries are reported and preserved. |
| Privilege | No `sudo`, `pkexec`, system-Python modification, service unit, sudoers policy, or passwordless privilege path. |
| Desktop mutation | A query never changes the desktop. Reviewed exact-component installation and enablement are separate actions and use Omarchy's native lifecycle. |

## Corrective review checklist

The repository is public and submission issue
[`HANCORE-linux/omarchy-plugin-marketplace#2039`](https://github.com/HANCORE-linux/omarchy-plugin-marketplace/issues/2039)
is the authoritative review thread. The initial 0.1.0 candidate was marked
`needs-fixes` because future package-index state could execute code during the
in-panel build. Version 0.1.1 replaces that path with the verified bundle
described above.

1. Freeze a clean corrective release commit after CI, current Omarchy validation, a real
   Omarchy/Hyprland visual smoke, and a fresh current-marketplace baseline.
2. Confirm the repository root contains `manifest.json`, `README.md`,
   `LICENSE`, installation and removal directions, and the owned root preview.
3. Confirm `Univeracity/limitless-omarchy` remains public, active, and
   unarchived.
4. Record the full 40-character corrective `main` SHA. Do not push another commit
   while the submission is being reviewed unless the submission is deliberately
   rerun against the new SHA.
5. Comment on issue #2039 with the corrective SHA and the supply-chain,
   combined-MCP, and icon changes. Do not open a duplicate submission.
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
