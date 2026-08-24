# Compatibility

## Supported contract

This initial adapter targets Omarchy's Quattro plugin contract:

- plugin manifest schema version 1;
- a third-party, non-reserved panel and bar-widget identifier;
- QML panel and bar-widget entry points;
- native validation through the Omarchy plugin validation command; and
- native reload or discovery through the Omarchy shell rescan command.

The contract is pinned in CI to Omarchy commit
ed7bae4ac5a570e9df307486e0202fdafcc6ee24. Update that pin only after
checking changes to the plugin manifest, lifecycle, and validator behavior.

The reviewed runtime bundle ties the public Limitless Library core wheel to
commit bbd8d312151e01503c85bce40ebbb3fa22aee66d and an exact SHA-256 digest.
Update it only after reproducible wheel builds and this adapter's full test,
package, distribution, and bundle-verification checks pass.

## UI-owned runtime

The panel's explicit setup action requires the normal Omarchy desktop
environment to expose an absolute `XDG_DATA_HOME` and Python 3 with virtual
environment support. It verifies a complete hash lock, accepts binary
dependencies only, and installs the reviewed adapter and pinned core wheels only
into `XDG_DATA_HOME/limitless-omarchy/runtime`; no system-Python installation,
package build, Git checkout, or privileged action is required. The same explicit setup can configure the
current Omarchy default agent through a verified MCP adapter. Native client
commands are used when available; Antigravity CLI uses its documented global
MCP profile. It never edits a guessed configuration path, overwrites an
existing `limitless-omarchy` server, or blocks local use when a selected agent
is unavailable.

The first setup may use network access to fetch exact hash-approved binary
Python dependencies. The core and adapter wheels are shipped in the reviewed
plugin checkout and installed without index access. Local queries after setup use the runtime-owned
catalog and require no network or managed service. Managed queries occur only
after the owner explicitly connects from **Library** and submits an objective.

The panel stores its own agent-connection descriptor and report beneath the
same XDG data root. That state contains only the selected agent IDs and the
exact local MCP command/args. It is used to preserve user changes: if an owned
entry no longer matches, the panel reports it and does not update or remove it.

## Compatibility matching

The companion sends only the following receiver facts into a local Library
query:

- linux;
- omarchy;
- omarchy-plugin-schema-v1;
- omarchy-shell-ipc when an IPC ping succeeds;
- an explicitly supplied release identifier, if the caller has one; and
- toolchain values for plugin schema and shell availability.

The caller also supplies one short local-only objective. It is not a receiver
fact and is not exported during local reuse; it only disambiguates
otherwise-equal eligible local results.

No local profile is a claim that all arbitrary plugin code is safe. An exact
component must still be reviewed and deliberately enabled by the owner.

For a managed query, the adapter translates the same bounded profile into the
public receiver context: current host platform and architecture, Python
execution version, the `omarchy.plugin/v1` interface, and an Omarchy target.
An explicitly supplied numeric Omarchy release becomes an exact target range;
an unknown or nonnumeric release remains `any`, which requires a returned
component to declare correspondingly broad compatibility.
