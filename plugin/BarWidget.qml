import QtQuick
import qs.Commons
import qs.Ui

// The visible UI entry point. The panel owns setup and use; this widget only
// opens it through Omarchy's shell, just as other panel-backed bar widgets do.
BarWidget {
  id: root
  moduleName: "univeracity.limitless-library"

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  Component {
    id: segmentedMark

    Item {
      readonly property real blockSize: Math.max(2, Math.floor(width / 5))
      readonly property real rowStep: (height - blockSize) / 4
      readonly property real tipX: Math.round(width * 0.06)
      readonly property real innerX: Math.round(width * 0.25)
      readonly property real outerX: Math.round(width * 0.63)

      Repeater {
        model: [
          { x: parent.outerX, row: 0, tone: 1.30 },
          { x: parent.innerX, row: 1, tone: 1.16 },
          { x: parent.tipX, row: 2, tone: 1.00 },
          { x: parent.innerX, row: 3, tone: 1.16 },
          { x: parent.outerX, row: 4, tone: 1.30 }
        ]

        Rectangle {
          x: modelData.x
          y: Math.round(modelData.row * parent.rowStep)
          width: parent.blockSize
          height: parent.blockSize
          color: modelData.tone === 1.00
            ? Color.accent
            : Qt.lighter(Color.accent, modelData.tone)
          antialiasing: false
        }
      }
    }
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    iconComponent: segmentedMark
    tooltipText: "Limitless Library"

    onPressed: function(mouseButton) {
      if (!root.bar || mouseButton !== Qt.LeftButton) return
      root.bar.run("omarchy-shell shell toggle univeracity.limitless-library '{}'")
    }
  }
}
