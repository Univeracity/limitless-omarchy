# Compatibility

## Supported contract

This initial adapter targets Omarchy's Quattro plugin contract:

- plugin manifest schema version 1;
- a third-party, non-reserved panel and bar-widget identifier;
- QML panel and bar-widget entry points;
- native validation through the Omarchy plugin validation command; and
- native reload or discovery through the Omarchy shell rescan command.

The contract is pinned in CI to Omarchy commit
30f7a06090dc20dd1a4a8d0c99bfb8e2370df2ec. Update that pin only after
checking changes to the plugin manifest, lifecycle, and validator behavior.

The Python package also pins the public Limitless Library core to commit
0a400fd27eac71fceb900c09efef784acb8a2f75. Update it only after running this
adapter's full test, package, and distribution checks against the candidate
core revision.

## UI-owned runtime

The panel's explicit setup action requires the normal Omarchy desktop
environment to expose an absolute `XDG_DATA_HOME` and Python 3 with virtual
environment support. It installs the reviewed adapter and pinned core only
into `XDG_DATA_HOME/limitless-omarchy/runtime`; no system-Python installation,
privileged action, or agent-side MCP configuration is supported or required.

The first setup may use network access to resolve the pinned public core and
its Python dependencies. Local queries after setup use the owner-selected
catalog and require no network or managed service. Managed queries occur only
after the owner expands that UI section and selects Inspect or Query.

## Compatibility matching

The companion sends only the following receiver facts into a local Library
query:

- linux;
- omarchy;
- omarchy-plugin-schema-v1;
- omarchy-shell-ipc when an IPC ping succeeds;
- an explicitly supplied release identifier, if the caller has one; and
- toolchain values for plugin schema and shell availability.

No local profile is a claim that all arbitrary plugin code is safe. An exact
component must still be reviewed and deliberately enabled by the owner.

For a managed query, the adapter translates the same bounded profile into the
public receiver context: current host platform and architecture, Python
execution version, the `omarchy.plugin/v1` interface, and an Omarchy target.
An explicitly supplied numeric Omarchy release becomes an exact target range;
an unknown or nonnumeric release remains `any`, which requires a returned
component to declare correspondingly broad compatibility.
