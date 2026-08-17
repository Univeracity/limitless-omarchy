import QtQuick
import qs.Commons
import qs.Ui

// Shared panel body. Keeping the visible surface separate from its Wayland
// container lets the same production QML be rendered in an ordinary window
// for visual regression inspection.
Item {
  id: root

  property var panel: null
  readonly property bool commandRunning: panel ? panel.commandRunning : false

  implicitWidth: 480
  implicitHeight: content.implicitHeight + 40

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
      text: root.panel ? root.panel.headline : ""
      color: Color.popups.text
      font.family: Style.font.family
      font.pixelSize: Style.font.heading
      font.bold: true
    }

    Text {
      width: 440
      wrapMode: Text.Wrap
      text: root.panel ? root.panel.detail : ""
      color: Color.popups.text
      opacity: 0.8
      font.family: Style.font.family
      font.pixelSize: Style.font.body
    }

    Text {
      visible: root.panel && root.panel.selectionReference !== ""
      width: 440
      elide: Text.ElideRight
      text: root.panel ? root.panel.selectionReference : ""
      color: Color.accent
      opacity: 0.8
      font.family: Style.font.family
      font.pixelSize: Style.font.bodySmall
    }

    Text {
      visible: root.panel && root.panel.catalogPath !== ""
      width: 440
      wrapMode: Text.WrapAnywhere
      text: root.panel ? "Catalog: " + root.panel.catalogPath : ""
      color: Color.popups.text
      opacity: 0.55
      font.family: Style.font.family
      font.pixelSize: Style.font.caption
    }

    Text {
      visible: root.panel && root.panel.errorText !== ""
      width: 440
      wrapMode: Text.Wrap
      text: root.panel ? root.panel.errorText : ""
      color: Color.urgent
      font.family: Style.font.family
      font.pixelSize: Style.font.bodySmall
    }

    Text {
      visible: root.commandRunning
      width: 440
      wrapMode: Text.Wrap
      text: root.panel && root.panel.operation === "setup"
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
      text: root.panel && root.panel.runtimeReady ? "Local catalog" : "No global installation"
      color: Color.popups.text
      font.family: Style.font.family
      font.pixelSize: Style.font.bodySmall
      font.bold: true
    }

    Rectangle {
      visible: root.panel && root.panel.runtimeReady
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
        text: root.panel ? root.panel.catalogPath : ""
        color: Color.popups.text
        font.family: Style.font.family
        font.pixelSize: Style.font.bodySmall
        selectByMouse: true
        onTextEdited: if (root.panel) root.panel.catalogPath = text

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
        text: root.panel && root.panel.runtimeReady ? "Update local runtime" : "Install local runtime"
        bordered: true
        focusable: true
        enabled: !root.commandRunning
        onClicked: if (root.panel) root.panel.installRuntime()
      }

      Button {
        width: 216
        height: Math.max(34, Style.spacing.controlHeight)
        text: "Try included example"
        bordered: true
        focusable: true
        enabled: root.panel && root.panel.runtimeReady && !root.commandRunning
        onClicked: if (root.panel) root.panel.queryExample()
      }
    }

    Button {
      visible: root.panel && root.panel.runtimeReady
      width: 440
      height: Math.max(34, Style.spacing.controlHeight)
      text: "Query local catalog"
      bordered: true
      focusable: true
      enabled: !root.commandRunning
      onClicked: if (root.panel) root.panel.queryCatalog()
    }

    Text {
      width: 440
      wrapMode: Text.Wrap
      text: root.panel && root.panel.runtimeReady
        ? "Local decisions stay on this machine. Review and enable desktop changes explicitly."
        : "Setup creates a per-user runtime under XDG data. It never installs globally or publishes work."
      color: Color.popups.text
      opacity: 0.65
      font.family: Style.font.family
      font.pixelSize: Style.font.bodySmall
    }
  }
}
