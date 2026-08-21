# Runtime smoke test

Run this only in a real Omarchy Quattro desktop session after reviewing,
installing, and explicitly enabling the plugin.

1. Open the **Limitless Library** bar button.
2. Select **Install local runtime** and wait for the panel to say "Local
   Library ready." This creates only its XDG-scoped runtime.
3. Select **Try included example**.

Confirm all of the following manually:

1. The panel opens from the bar without a Quickshell error.
2. Setup does not request elevated access or alter the system Python.
3. The included example returns a source-free method.
4. An owner can paste an absolute catalog path and query it from the panel.
5. Closing with Escape clears the panel.
6. No desktop customization was installed, enabled, updated, removed, or
   shared by the panel.

If the installed release includes official service trust material, also confirm:

1. Expanding **Use Limitless service (optional)** makes no request by itself.
2. **Enable official service** requires no profile path, account, or API key
   and establishes the private installation identity automatically.
3. **Inspect trust boundary** verifies the activation without sending an
   objective.
4. A managed query clears the objective after dispatch.
5. A signed selection, explicit abstention, or availability fallback is shown
   without changing the local catalog or enabling a plugin.
6. For a format-aware exact selection, **Prepare verified plugin review**
   displays an owner-only review tree and Omarchy's native validation result;
   confirm that the plugin remains neither installed nor enabled.

For lower-level, non-mutating validation of a checked-out repository, the
optional companion smoke command remains available:

    scripts/smoke-omarchy-panel --catalog ./examples/catalog --summon

It validates the repository with Omarchy's native validator, queries the
supplied catalog through the CLI, then opens an already-installed panel. It
does not replace the UI-owned setup and use path above.

Record the Omarchy release and the tested Quattro commit with any issue. Do
not treat this smoke test as a security audit of arbitrary QML or shell code.

## Headless regression harness

`tests/runtime/` contains an isolated Quickshell + Wayland harness for
maintainers. It runs the actual `plugin/Panel.qml` against its setup-required
state and asserts the panel's open, result, and close lifecycle. Its Ubuntu
image compiles Quickshell v0.3.0 with wlroots
layer-shell support; it is intentionally a maintainer test aid rather than a
user installation path.

The harness uses a headless compositor, so it validates the loaded QML,
runtime-process result, and lifecycle state. It does not replace the visual
check in a real Omarchy/Hyprland session, where the compositor provides the
actual layer-shell protocol and display integration.
