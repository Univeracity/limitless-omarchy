# Clipboard input

The objective and optional Omarchy release fields use a shared plain-text
TextEdit editor. They preserve native cursor movement, selection, copy/cut,
Unicode input-method composition, and undo/redo. Input is single-line and
limited to 480 Unicode characters.

On Qt 6.11.2 and 6.12.0, editable TextInput and TextField can fetch foreign
clipboard text automatically while updating `canPaste`. This occurs before
field-length validation and does not require a paste gesture. TextEdit's
plain-text availability check inspects offered formats without retrieving
the text payload. This fix applies to both plugin-owned editors, including
the optional field when hidden; it does not change unrelated host controls.

## Explicit paste

The editor intercepts Ctrl+V and Shift+Insert before native paste runs.
Middle-button press and release are intercepted for bounded primary-selection
paste. The Library's Paste button uses the same path. The bare TextEdit creates
no native context menu or drag-and-drop insertion path; the wrapper never calls
native `paste()`.

After an explicit gesture, the panel starts system Python with isolated startup
(`-I`) and the shipped standard-library helper. It invokes `wl-paste` using a
fixed argument vector, with no shell or clipboard-derived command arguments.
Only one transfer can run at a time.

The reader:

- accepts at most 2048 bytes, plus one byte to detect overflow before decoding;
- applies one monotonic two-second deadline to reading and process completion,
  including silent and slowly streaming offers;
- validates UTF-8, rejects control characters and overlong text, and turns line
  breaks and tabs into spaces;
- inherits a 64 MiB address-space limit, two CPU seconds, and a 32-descriptor
  limit into the transfer;
- terminates its owned process group on success, failure, or cancellation; and
- wraps the transfer in an independent GNU `timeout --signal=KILL` deadline so
  abrupt controller termination cannot leave a stalled `wl-paste` running.

The panel collects only the helper's bounded JSON response. Clipboard-producer
stderr is discarded. A failure leaves text and selection unchanged and reports
a local error. A reply is discarded if typing, navigation, selection, focus,
visibility, or enabled state changed while the read was pending. A successful
selection replacement remains one native undo operation.

Paste needs `wl-clipboard` and GNU coreutils. It installs nothing, uses no
elevated privileges, starts no persistent watcher or service, and sends no
clipboard text to a network endpoint. The Library objective reaches the service
only when the user separately chooses a public query. Missing dependencies
disable paste with an error; native typing remains available.

## Regression checks

`tests/test_objective_input_qt.py` runs the actual shared component under native
Qt Quick. An instrumented MIME offer records zero payload retrievals on a
clipboard change; an unguarded TextInput positive control reproduces the read.
The suite also exercises native Unicode/IME editing, intercepted keyboard and
middle-click paste, selection replacement and undo/redo, limits, and stale
results. CI runs these checks on Qt 6.11.2 and 6.12.0.

`tests/test_clipboard.py` uses private stub providers to check normal text,
exact-limit and oversized input, endless streams, silence, slow streams,
invalid UTF-8 and controls, cancellation, and abrupt controller termination.
Tests do not read the user's clipboard. The plugin contract gate also rejects
reintroduced TextInput/TextField controls and requires plain-text labels.

These focused offscreen and subprocess checks are not a full live desktop
integration test or a security audit.

## Review precedent

The marketplace reviewer accepted plain TextEdit with bounded explicit paste
for [Fishing Conditions](https://github.com/omacom/omarchy-plugin-marketplace/issues/10868#issuecomment-6107146003)
and [RAMen](https://github.com/omacom/omarchy-plugin-marketplace/issues/11063#issuecomment-6113961836).
The same review history rejects character limits alone, editable-on-focus
TextInput, and a TextEdit replacement that still uses unbounded native paste.
Those decisions inform this implementation; they do not approve this snapshot.
