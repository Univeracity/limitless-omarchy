# Omarchy marketplace submission and verification

The `0.2.0` alpha is published on GitHub. Its marketplace update is pending in
[`omacom/omarchy-plugin-marketplace#10975`](https://github.com/omacom/omarchy-plugin-marketplace/issues/10975).
The existing verified listing remains at `0.1.1` until the update is approved.
This guide records the review boundary and the process for qualifying a newer
commit; it does not claim a security certification.

Authoritative process references:

- [Marketplace submission guide](https://github.com/omacom/omarchy-plugin-marketplace/blob/main/SUBMISSION.md)
- [Marketplace verification definition](https://github.com/omacom/omarchy-plugin-marketplace/blob/main/VERIFICATION.md)
- [Marketplace security baseline](https://github.com/omacom/omarchy-plugin-marketplace/blob/main/SECURITY.md)
- [Official Omarchy shell-plugin guide](https://github.com/omacom/omarchy/blob/c352b62d67456f56ca898d0e23effc1b20c25ca6/manual/32-shell-plugins.md)

## Listing metadata

- Repository: `https://github.com/Univeracity/limitless-omarchy`
- Plugin ID: `univeracity.limitless-library`
- Category: `Productivity`
- Tags: `ai`, `quickshell`, `security`
- License: Apache-2.0

The initial listing was established through
[#2039](https://github.com/omacom/omarchy-plugin-marketplace/issues/2039).
The plugin ID is its permanent marketplace identity and should not change.

## Maintainer notes

For an update, post these notes as a separate comment on the review issue.
Preserve the verification form's exact headings; it has no **Maintainer notes**
field.

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
> Limitless Library commit `b9249e8de3e2cf558b70719dcd6e7a2ec44dd352`.
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

CI pins marketplace scanner commit
`ef66cc1aa925bf17491ba485a95b96a52daacf83`. The release preflight against
that pin on 2026-10-09 and the marketplace update reports on 2026-10-10
produced:

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

The update issue's bot reports record the current scanner policy and exact
target commit. A passing pinned CI check does not replace those fresh reports
or the required maintainer review.

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

## Update review checklist

The repository is public. The initial 0.1.0 candidate in
[#2039](https://github.com/omacom/omarchy-plugin-marketplace/issues/2039) was marked
`needs-fixes` because future package-index state could execute code during the
in-panel build. Version 0.1.1 replaced that path with the verified bundle. Version 0.2.0
retains that setup boundary and bundles the current core fixes, canonical method
publication, local fallback, streamlined Library and Agents views, and in-panel
sharing controls.
The current update review belongs in
[#10975](https://github.com/omacom/omarchy-plugin-marketplace/issues/10975).

1. Freeze a clean release commit after CI, current Omarchy validation, a real
   Omarchy/Hyprland visual smoke, and a fresh current-marketplace baseline.
2. Confirm the repository root contains `manifest.json`, `README.md`,
   `LICENSE`, installation and removal directions, and the owned root preview.
3. Confirm `Univeracity/limitless-omarchy` remains public, active, and
   unarchived.
4. Record the full 40-character target `main` SHA. Do not push another commit
   while the submission is being reviewed unless the submission is deliberately
   rerun against the new SHA.
5. Set the current update issue's **Target commit** to that SHA. For a future
   update without an open review, use the marketplace's **Plugin verification**
   form and choose **Verify and publish a newer upstream commit**. Keep the six
   form headings intact and put supporting notes in a separate comment. Do not
   open a duplicate review for the same update.
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
