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
3cc4839f87202422541a6aaa57a97d635f87f409. Update it only after running this
adapter's full test, package, and distribution checks against the candidate
core revision.

## UI-owned runtime

The panel's explicit setup action requires the normal Omarchy desktop
environment to expose an absolute `XDG_DATA_HOME` and Python 3 with virtual
environment support. It installs the reviewed adapter and pinned core only
into `XDG_DATA_HOME/limitless-omarchy/runtime`; no system-Python installation,
privileged action, or agent-side MCP configuration is supported or required.

The first setup may use network access to resolve the pinned public core and
its Python dependencies. Queries after setup use the owner-selected local
catalog; they do not require network access or a managed Limitless service.

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
