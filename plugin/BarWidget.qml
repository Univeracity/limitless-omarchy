import QtQuick
import qs.Ui

// The visible UI entry point. The panel owns setup and use; this widget only
// opens it through Omarchy's shell, just as other panel-backed bar widgets do.
BarWidget {
  id: root
  moduleName: "univeracity.limitless-library"

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "<"
    tooltipText: "Limitless Library"

    onPressed: function(mouseButton) {
      if (!root.bar || mouseButton !== Qt.LeftButton) return
      root.bar.run("omarchy-shell shell toggle univeracity.limitless-library '{}'")
    }
  }
}
