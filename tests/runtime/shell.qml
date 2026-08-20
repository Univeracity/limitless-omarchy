import QtQuick
import Quickshell
import Quickshell.Io

// A minimal real Quickshell host. It loads the shipped panel, exercises its
// open/query/close lifecycle, and writes only a compact assertion result.
ShellRoot {
  id: root

  property string panelPath: Quickshell.env("LIMITLESS_PANEL_PATH")
  property string pluginRoot: Quickshell.env("LIMITLESS_PLUGIN_ROOT")
  property string resultPath: Quickshell.env("LIMITLESS_PANEL_RESULT")
  property string payloadJson: Quickshell.env("LIMITLESS_PANEL_PAYLOAD") || "{}"
  property bool visualHold: Quickshell.env("LIMITLESS_PANEL_VISUAL_HOLD") === "1"
  property string visualAction: Quickshell.env("LIMITLESS_PANEL_VISUAL_ACTION")
  property string failure: ""

  property var shellBridge: QtObject {
    function hide(_pluginId) {
      if (panel.item) panel.item.close()
    }
  }
  property var manifestBridge: ({
    id: "univeracity.limitless-library",
    __sourceDir: root.pluginRoot
  })

  FileView {
    id: resultFile
    path: root.resultPath
    atomicWrites: true
    printErrors: true
  }

  Timer {
    id: finishTimer
    interval: 80
    repeat: false
    onTriggered: Qt.quit()
  }

  Timer {
    id: inspectTimer
    interval: root.visualHold ? 3500 : 1200
    repeat: false
    onTriggered: root.finish()
  }

  Timer {
    id: actionTimer
    interval: 1500
    repeat: false
    onTriggered: {
      if (root.visualAction === "example" && panel.item) panel.item.queryExample()
      if (root.visualAction === "service" && panel.item) {
        panel.item.runtimeReady = true
        panel.item.serviceExpanded = true
        panel.item.headline = "Local Library ready"
        panel.item.detail = "Local reuse remains available. Managed discovery is an explicit opt-in."
      }
    }
  }

  Loader {
    id: panel
    source: root.panelPath
    onStatusChanged: {
      if (status === Loader.Error) {
        root.failure = "The panel could not be loaded by Quickshell."
        root.finish()
      }
    }
    onLoaded: {
      item.shell = root.shellBridge
      item.manifest = root.manifestBridge
      item.open(root.payloadJson)
      if (root.visualHold && root.visualAction !== "") actionTimer.start()
      inspectTimer.start()
    }
  }

  function finish() {
    var snapshot = {
      ok: failure === "" && panel.status === Loader.Ready && panel.item !== null,
      failure: failure,
      loaderStatus: panel.status,
      opened: panel.item ? panel.item.opened : false,
      runtimeReady: panel.item ? panel.item.runtimeReady : false,
      disposition: panel.item ? panel.item.disposition : "",
      headline: panel.item ? panel.item.headline : "",
      detail: panel.item ? panel.item.detail : "",
      selectionReference: panel.item ? panel.item.selectionReference : "",
      serviceExpanded: panel.item ? panel.item.serviceExpanded : false,
      errorText: panel.item ? panel.item.errorText : ""
    }
    if (visualHold) {
      resultFile.setText(JSON.stringify(snapshot))
      return
    }
    if (panel.item) {
      panel.item.close()
      snapshot.closed = !panel.item.opened
    } else {
      snapshot.closed = false
    }
    resultFile.setText(JSON.stringify(snapshot))
    finishTimer.start()
  }
}
