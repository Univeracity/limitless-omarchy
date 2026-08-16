# Runtime smoke test

Run this only in a real Omarchy Quattro desktop session after reviewing,
installing, and explicitly enabling the plugin. It does not install, enable,
update, remove, or share anything.

    scripts/smoke-omarchy-panel --catalog ./examples/catalog

That command validates the repository using Omarchy's native validator and
queries the local catalog. To open the already installed panel after those
checks:

    scripts/smoke-omarchy-panel --catalog ./examples/catalog --summon

Confirm all of the following manually:

1. The panel opens without a Quickshell error.
2. The panel says a source-free method is available for the bundled catalog.
3. The catalog path shown is the supplied local path.
4. Closing with Escape clears the panel.
5. No plugin was installed, enabled, updated, removed, or shared by the
   smoke command.

Record the Omarchy release and the tested Quattro commit with any issue. Do
not treat this smoke test as a security audit of arbitrary QML or shell code.

## Headless regression harness

`tests/runtime/` contains an isolated Quickshell + Wayland harness for
maintainers. It runs the actual `plugin/Panel.qml` against the bundled local
method catalog and asserts the panel's open, local-query, result, and close
lifecycle. Its Ubuntu image compiles Quickshell v0.3.0 with wlroots
layer-shell support; it is intentionally a maintainer test aid rather than a
user installation path.

The harness uses a headless compositor, so it validates the loaded QML,
companion-process result, and lifecycle state. It does not replace the visual
check in a real Omarchy/Hyprland session, where the compositor provides the
actual layer-shell protocol and display integration.
