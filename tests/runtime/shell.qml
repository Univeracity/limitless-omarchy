import QtQuick
import Quickshell
import Quickshell.Io

// A minimal real Quickshell host. It loads the shipped panel, exercises its
// open/query/close lifecycle, and writes only a compact assertion result.
ShellRoot {
  id: root

  property string panelPath: Quickshell.env("LIMITLESS_PANEL_PATH")
  property string resultPath: Quickshell.env("LIMITLESS_PANEL_RESULT")
  property string payloadJson: Quickshell.env("LIMITLESS_PANEL_PAYLOAD") || "{}"
  property string failure: ""

  property var shellBridge: QtObject {
    function hide(_pluginId) {
      if (panel.item) panel.item.close()
    }
  }
  property var manifestBridge: ({ id: "univeracity.limitless-library" })

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
    interval: 1200
    repeat: false
    onTriggered: root.finish()
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
      inspectTimer.start()
    }
  }

  function finish() {
    var snapshot = {
      ok: failure === "" && panel.status === Loader.Ready && panel.item !== null,
      failure: failure,
      loaderStatus: panel.status,
      opened: panel.item ? panel.item.opened : false,
      disposition: panel.item ? panel.item.disposition : "",
      headline: panel.item ? panel.item.headline : "",
      detail: panel.item ? panel.item.detail : "",
      selectionReference: panel.item ? panel.item.selectionReference : "",
      errorText: panel.item ? panel.item.errorText : ""
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
