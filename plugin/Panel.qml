import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons
import qs.Ui

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
    implicitWidth: 480
    implicitHeight: content.implicitHeight + 40
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

      Column {
        id: content
        anchors.fill: parent
        anchors.margins: 20
        spacing: 12

        Text {
          text: "LIMITLESS LIBRARY"
          color: Color.accent
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
          font.bold: true
        }

        Text {
          text: root.headline
          color: Color.popups.text
          font.family: Style.font.family
          font.pixelSize: Style.font.heading
          font.bold: true
        }

        Text {
          width: 440
          wrapMode: Text.Wrap
          text: root.detail
          color: Color.popups.text
          opacity: 0.8
          font.family: Style.font.family
          font.pixelSize: Style.font.body
        }

        Text {
          visible: root.selectionReference !== ""
          width: 440
          elide: Text.ElideRight
          text: root.selectionReference
          color: Color.accent
          opacity: 0.8
          font.family: Style.font.family
          font.pixelSize: Style.font.bodySmall
        }

        Text {
          visible: root.catalogPath !== ""
          width: 440
          wrapMode: Text.WrapAnywhere
          text: "Catalog: " + root.catalogPath
          color: Color.popups.text
          opacity: 0.55
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
        }

        Text {
          visible: root.errorText !== ""
          width: 440
          wrapMode: Text.Wrap
          text: root.errorText
          color: Color.urgent
          font.family: Style.font.family
          font.pixelSize: Style.font.bodySmall
        }

        Text {
          visible: root.commandRunning
          width: 440
          wrapMode: Text.Wrap
          text: root.operation === "setup"
            ? "Preparing the isolated local runtime…"
            : "Checking local reuse…"
          color: Color.accent
          font.family: Style.font.family
          font.pixelSize: Style.font.bodySmall
        }

        Rectangle {
          width: 440
          height: 1
          color: Color.popups.border
          opacity: 0.65
        }

        Text {
          width: 440
          text: root.runtimeReady ? "Local catalog" : "No global installation"
          color: Color.popups.text
          font.family: Style.font.family
          font.pixelSize: Style.font.bodySmall
          font.bold: true
        }

        Rectangle {
          visible: root.runtimeReady
          width: 440
          height: Math.max(34, Style.spacing.controlHeight)
          radius: Style.cornerRadius
          color: Color.popups.background
          border.color: catalogInput.activeFocus ? Color.accent : Color.popups.border
          border.width: 1

          TextInput {
            id: catalogInput
            anchors.fill: parent
            anchors.leftMargin: 10
            anchors.rightMargin: 10
            verticalAlignment: TextInput.AlignVCenter
            clip: true
            text: root.catalogPath
            color: Color.popups.text
            font.family: Style.font.family
            font.pixelSize: Style.font.bodySmall
            selectByMouse: true
            onTextEdited: root.catalogPath = text

            Text {
              anchors.fill: parent
              verticalAlignment: Text.AlignVCenter
              visible: catalogInput.text === ""
              text: "/absolute/path/to/local-catalog"
              color: Color.popups.text
              opacity: 0.45
              font: catalogInput.font
            }
          }
        }

        Row {
          width: 440
          spacing: 8

          Button {
            width: 216
            height: Math.max(34, Style.spacing.controlHeight)
            text: root.runtimeReady ? "Update local runtime" : "Install local runtime"
            bordered: true
            focusable: true
            enabled: !root.commandRunning
            onClicked: root.installRuntime()
          }

          Button {
            width: 216
            height: Math.max(34, Style.spacing.controlHeight)
            text: "Try included example"
            bordered: true
            focusable: true
            enabled: root.runtimeReady && !root.commandRunning
            onClicked: root.queryExample()
          }
        }

        Button {
          visible: root.runtimeReady
          width: 440
          height: Math.max(34, Style.spacing.controlHeight)
          text: "Query local catalog"
          bordered: true
          focusable: true
          enabled: !root.commandRunning
          onClicked: root.queryCatalog()
        }

        Text {
          width: 440
          wrapMode: Text.Wrap
          text: root.runtimeReady
            ? "Local decisions stay on this machine. Review and enable desktop changes explicitly."
            : "Setup creates a per-user runtime under XDG data. It never installs globally or publishes work."
          color: Color.popups.text
          opacity: 0.65
          font.family: Style.font.family
          font.pixelSize: Style.font.bodySmall
        }
      }

      MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.RightButton
        onClicked: root.dismiss()
      }
    }
  }
}
