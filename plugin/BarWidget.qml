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
      // Match the panel mark's directly staggered block rhythm: each row
      // advances by exactly one block, with no disconnected middle gap.
      readonly property real blockSize: Math.max(
        2,
        Math.floor(Math.min(width / 3, height / 5))
      )
      readonly property real markWidth: blockSize * 3
      readonly property real markHeight: blockSize * 5
      readonly property real originX: Math.round((width - markWidth) / 2)
      readonly property real originY: Math.round((height - markHeight) / 2)

      Repeater {
        model: [
          { column: 2, row: 0, tone: 1.30 },
          { column: 1, row: 1, tone: 1.16 },
          { column: 0, row: 2, tone: 1.00 },
          { column: 1, row: 3, tone: 1.16 },
          { column: 2, row: 4, tone: 1.30 }
        ]

        Rectangle {
          x: parent.originX + modelData.column * parent.blockSize
          y: parent.originY + modelData.row * parent.blockSize
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
