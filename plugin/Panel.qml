import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons
import qs.Ui
import "." as Local

// Standalone Quattro panel. It owns local setup and local use; the bundled
// runtime creates an isolated CLI only after the owner explicitly asks it to.
Item {
  id: root

  property var shell: null
  property var manifest: null
  property bool opened: false
  property string catalogPath: ""
  property bool runtimeReady: false
  property string headline: "Set up Limitless Library"
  property string detail: "Create an isolated local runtime to begin. Nothing will be shared."
  property string disposition: "status"
  property string selectionReference: ""
  property string errorText: ""
  property string commandOutput: ""
  property string commandError: ""
  property string operation: ""
  readonly property string pluginRoot: manifest && manifest.__sourceDir
    ? String(manifest.__sourceDir) : ""
  readonly property bool commandRunning: command.running

  function open(payloadJson) {
    var payload = {}
    try { payload = JSON.parse(payloadJson || "{}") || {} } catch (e) {}
    if (payload.catalogPath !== undefined) catalogPath = String(payload.catalogPath)
    opened = true
    refresh()
    Qt.callLater(function() { if (opened) keyCatcher.forceActiveFocus() })
  }

  function close() {
    opened = false
    if (command.running) command.running = false
  }

  function dismiss() {
    if (shell && typeof shell.hide === "function")
      shell.hide((manifest && manifest.id) || "univeracity.limitless-library")
    else close()
  }

  function refresh() {
    runRuntime("status", [])
  }

  function installRuntime() {
    runRuntime("setup", [])
  }

  function queryCatalog() {
    if (catalogPath.trim() === "") {
      errorText = "Choose a readable local catalog before querying it."
      return
    }
    runRuntime("query", ["--catalog", catalogPath.trim()])
  }

  function queryExample() {
    runRuntime("query-demo", [])
  }

  function runRuntime(nextOperation, arguments) {
    if (command.running) return
    errorText = ""
    commandOutput = ""
    commandError = ""
    operation = nextOperation
    if (pluginRoot === "") {
      errorText = "The Omarchy plugin root is unavailable. Reinstall this reviewed plugin before continuing."
      return
    }
    command.command = ["bash", pluginRoot + "/scripts/limitless-omarchy-runtime", nextOperation,
      "--plugin-root", pluginRoot].concat(arguments)
    command.running = true
  }

  function applyResult(raw) {
    var value = {}
    try { value = JSON.parse(String(raw || "")) } catch (e) {
      errorText = "The local adapter returned invalid JSON."
      return
    }
    if (value.schemaVersion === "limitless.omarchy-status/0.1") {
      disposition = "status"
      runtimeReady = String(value.mode || "") === "local-only"
      headline = runtimeReady ? "Local Library ready" : "Set up Limitless Library"
      detail = runtimeReady
        ? "Choose a local catalog below, or inspect the included example. The service is not connected."
        : "Create an isolated local runtime to begin. Nothing will be shared."
      selectionReference = ""
      return
    }
    runtimeReady = true
    disposition = String(value.disposition || "abstain")
    var selected = value.decision && value.decision.selected ? value.decision.selected : null
    selectionReference = selected && selected.capsule
      ? String(selected.capsule.id || "") + " @ " + String(selected.capsule.version || "")
      : ""
    if (disposition === "exact-component") {
      var files = selected && selected.offer && selected.offer.files ? selected.offer.files : []
      headline = "Exact component available"
      detail = String(files.length) + " sealed file" + (files.length === 1 ? "" : "s")
        + " available. Review the source and use Omarchy's native install and validation flow."
    } else if (disposition === "source-free-method") {
      var method = selected && selected.offer ? selected.offer.method : null
      headline = "Source-free method available"
      detail = method && method.summary
        ? String(method.summary)
        : "Apply the method locally; it does not deliver another user's source."
    } else {
      headline = "Start fresh"
      detail = "No eligible local result was selected. No candidate details were disclosed."
    }
  }

  Process {
    id: command
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.commandOutput = String(text || "")
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.commandError = String(text || "").trim()
    }
    onExited: function(exitCode) {
      if (!root.opened) return
      if (exitCode === 0) root.applyResult(root.commandOutput)
      else root.errorText = root.commandError !== "" ? root.commandError : "The local runtime is unavailable."
      root.operation = ""
    }
  }

  PanelWindow {
    visible: root.opened
    implicitWidth: content.implicitWidth
    implicitHeight: content.implicitHeight
    anchors { top: true; right: true }
    margins { top: 44; right: 20 }
    color: Color.popups.background
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.namespace: "limitless-library"
    WlrLayershell.layer: WlrLayer.Top
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

    Item {
      id: keyCatcher
      anchors.fill: parent
      focus: true
      Keys.onEscapePressed: root.dismiss()

      Rectangle {
        anchors.fill: parent
        color: "transparent"
        border.color: Color.popups.border
        border.width: 1
        radius: Style.cornerRadius
      }

      Local.PanelContents {
        id: content
        anchors.fill: parent
        panel: root
      }

      MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.RightButton
        onClicked: root.dismiss()
      }
    }
  }
}
