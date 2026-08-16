import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons

// Standalone Quattro panel. It surfaces a bounded local decision; the
// companion CLI owns profile derivation and catalog interaction.
Item {
  id: root

  property var shell: null
  property var manifest: null
  property bool opened: false
  property string catalogPath: ""
  property string headline: "Local-only"
  property string detail: "No catalog query has been requested."
  property string disposition: "status"
  property string selectionReference: ""
  property string errorText: ""

  function open(payloadJson) {
    var payload = {}
    try { payload = JSON.parse(payloadJson || "{}") || {} } catch (e) {}
    catalogPath = payload.catalogPath === undefined ? "" : String(payload.catalogPath)
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
    errorText = ""
    command.running = false
    command.command = catalogPath === ""
      ? ["limitless-omarchy", "status"]
      : ["limitless-omarchy", "query", "--catalog", catalogPath]
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
      headline = "Local-only"
      detail = "The service is not connected. Nothing has been shared."
      selectionReference = ""
      return
    }
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
      onStreamFinished: root.applyResult(text)
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var message = String(text || "").trim()
        if (message !== "") root.errorText = message
      }
    }
    onExited: function(exitCode) {
      if (!root.opened || exitCode === 0) return
      if (root.errorText === "") root.errorText = "The local adapter is unavailable."
    }
  }

  PanelWindow {
    visible: root.opened
    implicitWidth: 440
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
          width: 400
          wrapMode: Text.Wrap
          text: root.detail
          color: Color.popups.text
          opacity: 0.8
          font.family: Style.font.family
          font.pixelSize: Style.font.body
        }

        Text {
          visible: root.selectionReference !== ""
          width: 400
          elide: Text.ElideRight
          text: root.selectionReference
          color: Color.accent
          opacity: 0.8
          font.family: Style.font.family
          font.pixelSize: Style.font.bodySmall
        }

        Text {
          visible: root.catalogPath !== ""
          width: 400
          wrapMode: Text.WrapAnywhere
          text: "Catalog: " + root.catalogPath
          color: Color.popups.text
          opacity: 0.55
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
        }

        Text {
          visible: root.errorText !== ""
          width: 400
          wrapMode: Text.Wrap
          text: root.errorText
          color: Color.urgent
          font.family: Style.font.family
          font.pixelSize: Style.font.bodySmall
        }

        Rectangle {
          width: 400
          height: 1
          color: Color.popups.border
          opacity: 0.65
        }

        Text {
          width: 400
          wrapMode: Text.Wrap
          text: "Local decisions stay on this machine. Review and enable desktop changes explicitly."
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
