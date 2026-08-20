import QtQuick
import Quickshell
import Quickshell.Io

// Renders the production PanelContents in an ordinary Wayland window so a
// maintainer can inspect both ends of the bounded, scrollable surface without
// requiring a full Hyprland session.
ShellRoot {
  id: root

  property string panelContentsPath: Quickshell.env("LIMITLESS_PANEL_CONTENTS_PATH")
  property string outputDirectory: Quickshell.env("LIMITLESS_VISUAL_OUTPUT")

  property var panelState: QtObject {
    property bool commandRunning: false
    property bool runtimeReady: true
    property bool serviceExpanded: true
    property bool serviceReady: true
    property string headline: "Local Library ready"
    property string detail: "Local reuse remains available. Managed discovery is an explicit opt-in."
    property string selectionReference: ""
    property string catalogPath: "/home/user/.local/share/limitless/catalog"
    property string errorText: ""
    property string operation: ""
    property string serviceProfilePath: "/home/user/.config/limitless/service-profile.json"
    property string serviceObjective: "Find a recent customization that improves workspace focus"
    property string omarchyRelease: "2026.08"
    property string serviceAccessToken: ""
    property string serviceSummary: "Pinned service · standard data use · accepted policy"

    function installRuntime() {}
    function queryExample() {}
    function queryCatalog() {}
    function inspectService() {}
    function queryService() {}
  }

  FileView {
    id: resultFile
    path: root.outputDirectory + "/visual-result.json"
    atomicWrites: true
    printErrors: true
  }

  FloatingWindow {
    id: window
    visible: true
    implicitWidth: 480
    implicitHeight: 680
    color: "#101315"

    Loader {
      id: contents
      anchors.fill: parent
      source: root.panelContentsPath
      onLoaded: item.panel = root.panelState
    }
  }

  Timer {
    id: topTimer
    interval: 1000
    running: true
    repeat: false
    onTriggered: {
      if (!contents.item) {
        resultFile.setText(JSON.stringify({ok: false, reason: "contents-not-loaded"}))
        Qt.quit()
        return
      }
      contents.item.grabToImage(function(result) {
        var topSaved = result.saveToFile(root.outputDirectory + "/service-top.png")
        var scroll = contents.item.children.length > 0 ? contents.item.children[0] : null
        if (scroll && scroll.contentY !== undefined)
          scroll.contentY = Math.max(0, scroll.contentHeight - scroll.height)
        root.topSaved = topSaved
        bottomTimer.start()
      }, Qt.size(480, 680))
    }
  }

  property bool topSaved: false

  Timer {
    id: bottomTimer
    interval: 250
    repeat: false
    onTriggered: {
      contents.item.grabToImage(function(result) {
        var bottomSaved = result.saveToFile(root.outputDirectory + "/service-bottom.png")
        resultFile.setText(JSON.stringify({
          ok: root.topSaved && bottomSaved,
          topSaved: root.topSaved,
          bottomSaved: bottomSaved
        }))
        Qt.quit()
      }, Qt.size(480, 680))
    }
  }
}
