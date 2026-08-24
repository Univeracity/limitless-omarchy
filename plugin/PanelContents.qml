import QtQuick
import QtQuick.Controls
import qs.Commons
import qs.Ui

// Shared panel body. The lifecycle is intentionally split into small
// surfaces so ordinary use does not begin inside a wall of setup controls.
// Keeping this separate from its Wayland container also permits real visual
// rendering in CI without a full Hyprland session.
Item {
  id: root

  property var panel: null
  readonly property bool commandRunning: panel ? panel.commandRunning : false
  readonly property int bodyWidth: 440
  readonly property int controlHeight: Math.max(34, Style.spacing.controlHeight)

  function heroMeta(fallback) {
    if (!root.commandRunning || !root.panel || root.panel.operation === "stats") return fallback
    return root.panel.operation === "setup" ? "Preparing local runtime" : "Checking Library status"
  }

  function scrollToTop() {
    panelFlick.contentY = panelFlick.originY
    Qt.callLater(function() { panelFlick.contentY = panelFlick.originY })
  }

  implicitWidth: 480
  implicitHeight: 680

  Connections {
    target: root.panel
    function onActiveSectionChanged() { root.scrollToTop() }
  }

  Component {
    id: brandIcon
    Item {
      implicitWidth: 30
      implicitHeight: 30

      Column {
        anchors.centerIn: parent
        spacing: -2

        Text {
          text: "    ██"
          color: Qt.lighter(Color.accent, 1.30)
          font.family: Style.font.family
          font.pixelSize: 6
          font.bold: true
        }

        Text {
          text: "  ██"
          color: Qt.lighter(Color.accent, 1.16)
          font.family: Style.font.family
          font.pixelSize: 6
          font.bold: true
        }

        Text {
          text: "██"
          color: Color.accent
          font.family: Style.font.family
          font.pixelSize: 6
          font.bold: true
        }

        Text {
          text: "  ██"
          color: Qt.lighter(Color.accent, 1.16)
          font.family: Style.font.family
          font.pixelSize: 6
          font.bold: true
        }

        Text {
          text: "    ██"
          color: Qt.lighter(Color.accent, 1.30)
          font.family: Style.font.family
          font.pixelSize: 6
          font.bold: true
        }
      }
    }
  }

  Component {
    id: univeracityIcon
    Item {
      implicitWidth: 36
      implicitHeight: 42

      Image {
        anchors.fill: parent
        anchors.margins: 1
        source: Qt.resolvedUrl("../assets/univeracity-logo.png")
        fillMode: Image.PreserveAspectFit
        smooth: true
        mipmap: true
      }
    }
  }

  Component {
    id: limitlessLibraryLogoIcon
    Item {
      implicitWidth: 42
      implicitHeight: 42

      Image {
        anchors.fill: parent
        source: Qt.resolvedUrl("../assets/limitless-library-logo.png")
        fillMode: Image.PreserveAspectFit
        smooth: true
        mipmap: true
      }
    }
  }

  component StatTile: BorderSurface {
    id: statTile
    property string label: ""
    property string value: "0"
    property bool highlighted: false
    property bool loading: false

    width: 216
    implicitHeight: 68
    color: highlighted
      ? Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, 0.10)
      : Color.popups.background
    borderSpec: Border.flat(
      highlighted ? Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, 0.42) : Color.popups.border,
      1
    )
    radius: Style.cornerRadius

    Column {
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
      anchors.leftMargin: 12
      anchors.rightMargin: 12
      spacing: 1

      Text {
        id: statValue
        text: statTile.loading ? "◒" : statTile.value
        color: statTile.highlighted ? Color.accent : Color.popups.text
        font.family: Style.font.family
        font.pixelSize: Style.font.title
        font.bold: true
        transformOrigin: Item.Center

        RotationAnimation on rotation {
          from: 0
          to: 360
          duration: 700
          loops: Animation.Infinite
          running: statTile.loading
          onRunningChanged: if (!running) statValue.rotation = 0
        }
      }

      Text {
        width: parent.width
        text: statTile.label.toUpperCase()
        color: Color.popups.text
        opacity: 0.58
        elide: Text.ElideRight
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
        font.bold: true
        font.letterSpacing: 0.7
      }
    }
  }

  component InlineMetric: Item {
    id: inlineMetric
    property string label: ""
    property string value: "0"
    property bool loading: false

    implicitHeight: 18

    Row {
      anchors.left: parent.left
      anchors.verticalCenter: parent.verticalCenter
      spacing: 4

      Text {
        text: inlineMetric.label
        color: Color.popups.text
        opacity: 0.58
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
      }

      Text {
        id: inlineMetricValue
        width: 18
        horizontalAlignment: Text.AlignHCenter
        text: inlineMetric.loading ? "◒" : inlineMetric.value
        color: Color.popups.text
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
        font.bold: true
        transformOrigin: Item.Center

        RotationAnimation on rotation {
          from: 0
          to: 360
          duration: 700
          loops: Animation.Infinite
          running: inlineMetric.loading
          onRunningChanged: if (!running) inlineMetricValue.rotation = 0
        }
      }
    }
  }

  Flickable {
    id: panelFlick
    anchors.fill: parent
    clip: true
    contentWidth: width
    contentHeight: content.implicitHeight + 20
    flickableDirection: Flickable.VerticalFlick
    boundsBehavior: Flickable.StopAtBounds
    interactive: contentHeight > height
    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

    Column {
      id: content
      x: 20
      y: 0
      width: root.bodyWidth
      spacing: 12

      // Keep padding inside the flow. Positioning the whole column at y=20
      // changes a Flickable's effective origin once a section becomes long
      // enough to scroll, which can clip the hero after changing tabs.
      Item {
        width: 1
        height: 8
      }

      PanelHero {
        visible: root.panel && root.panel.activeSection === "library"
        width: parent.width
        title: "Limitless Library"
        meta: root.heroMeta(root.panel ? root.panel.headline : "")
        detail: ""
        foreground: Color.popups.text
        fontFamily: Style.font.family
        iconComponent: brandIcon
      }

      PanelHero {
        visible: root.panel && root.panel.activeSection === "agents"
        width: parent.width
        title: "Limitless Library"
        meta: root.heroMeta("Agent connections")
        detail: ""
        foreground: Color.popups.text
        fontFamily: Style.font.family
        iconComponent: brandIcon
      }

      PanelHero {
        visible: root.panel && root.panel.activeSection === "service"
        width: parent.width
        title: "Limitless Library"
        meta: root.heroMeta("Public discovery")
        detail: ""
        foreground: Color.popups.text
        fontFamily: Style.font.family
        iconComponent: brandIcon
      }

      PanelHero {
        visible: root.panel && root.panel.activeSection === "stats"
        width: parent.width
        title: "Limitless Library"
        meta: "Quietly keeping score"
        detail: ""
        foreground: Color.popups.text
        fontFamily: Style.font.family
        iconComponent: brandIcon
      }

      PanelHero {
        visible: root.panel && root.panel.activeSection === "about"
        width: parent.width
        title: "Limitless Library"
        meta: "About the Library"
        detail: ""
        foreground: Color.popups.text
        fontFamily: Style.font.family
        iconComponent: brandIcon
      }

      Text {
        visible: root.panel && root.panel.activeSection === "library"
        width: parent.width
        wrapMode: Text.Wrap
        text: root.panel ? root.panel.detail : ""
        color: Color.popups.text
        opacity: 0.76
        font.family: Style.font.family
        font.pixelSize: Style.font.bodySmall
      }

      Text {
        visible: root.panel && root.panel.activeSection === "agents"
        width: parent.width
        wrapMode: Text.Wrap
        text: "Connect the Omarchy default, then add other agents only if needed."
        color: Color.popups.text
        opacity: 0.76
        font.family: Style.font.family
        font.pixelSize: Style.font.bodySmall
      }

      Text {
        visible: root.panel && root.panel.activeSection === "service"
        width: parent.width
        wrapMode: Text.Wrap
        text: "Search public and shared work without giving up local control."
        color: Color.popups.text
        opacity: 0.76
        font.family: Style.font.family
        font.pixelSize: Style.font.bodySmall
      }

      Text {
        visible: root.panel && root.panel.activeSection === "stats"
        width: parent.width
        wrapMode: Text.Wrap
        text: "See what Limitless has been doing in the background."
        color: Color.popups.text
        opacity: 0.76
        font.family: Style.font.family
        font.pixelSize: Style.font.bodySmall
      }

      Text {
        visible: root.panel && root.panel.activeSection === "about"
        width: parent.width
        wrapMode: Text.Wrap
        text: "Why reuse needs more than just search."
        color: Color.popups.text
        opacity: 0.76
        font.family: Style.font.family
        font.pixelSize: Style.font.bodySmall
      }

      Text {
        visible: root.panel && root.panel.selectionReference !== ""
        width: parent.width
        elide: Text.ElideRight
        text: root.panel ? root.panel.selectionReference : ""
        color: Color.accent
        opacity: 0.8
        font.family: Style.font.family
        font.pixelSize: Style.font.bodySmall
      }

      BorderSurface {
        visible: root.panel && root.panel.errorText !== ""
        width: parent.width
        implicitHeight: errorMessage.implicitHeight + 20
        color: Qt.rgba(Color.urgent.r, Color.urgent.g, Color.urgent.b, 0.10)
        borderSpec: Border.flat(Qt.rgba(Color.urgent.r, Color.urgent.g, Color.urgent.b, 0.35), 1)
        radius: Style.cornerRadius

        Text {
          id: errorMessage
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          anchors.margins: 10
          wrapMode: Text.Wrap
          text: root.panel ? root.panel.errorText : ""
          color: Color.urgent
          font.family: Style.font.family
          font.pixelSize: Style.font.bodySmall
        }
      }

      Row {
        width: parent.width
        spacing: 8

        Button {
          width: 96
          height: root.controlHeight
          text: "Library"
          selected: root.panel && root.panel.activeSection === "library"
          bordered: true
          focusable: true
          enabled: !root.commandRunning
          onClicked: if (root.panel) {
            root.panel.selectSection("library")
            root.scrollToTop()
          }
        }

        Button {
          width: 96
          height: root.controlHeight
          text: "Agents"
          selected: root.panel && root.panel.activeSection === "agents"
          bordered: true
          focusable: true
          enabled: root.panel && root.panel.runtimeReady && !root.commandRunning
          onClicked: if (root.panel) {
            root.panel.selectSection("agents")
            root.scrollToTop()
          }
        }

        Button {
          width: 96
          height: root.controlHeight
          text: "Service"
          selected: root.panel && root.panel.activeSection === "service"
          bordered: true
          focusable: true
          enabled: root.panel && root.panel.runtimeReady && !root.commandRunning
          onClicked: if (root.panel) {
            root.panel.selectSection("service")
            root.scrollToTop()
          }
        }

        Button {
          width: 96
          height: root.controlHeight
          text: "Stats"
          selected: root.panel && root.panel.activeSection === "stats"
          bordered: true
          focusable: true
          enabled: root.panel && root.panel.runtimeReady && !root.commandRunning
          onClicked: if (root.panel) {
            root.panel.selectSection("stats")
            root.scrollToTop()
          }
        }

        Button {
          width: 24
          height: root.controlHeight
          text: "?"
          tooltipText: "About Limitless Library"
          selected: root.panel && root.panel.activeSection === "about"
          bordered: true
          focusable: true
          enabled: !root.commandRunning
          onClicked: if (root.panel) {
            root.panel.selectSection("about")
            root.scrollToTop()
          }
        }
      }

      Rectangle {
        width: parent.width
        height: 1
        color: Color.popups.border
        opacity: 0.65
      }

      // Local Library -------------------------------------------------------
      Column {
        visible: root.panel && root.panel.activeSection === "library"
        width: parent.width
        spacing: 12

        PanelSectionHeader {
          width: parent.width
          text: root.panel && root.panel.runtimeReady ? "LOCAL REUSE" : "PRIVATE SETUP"
          foreground: Color.popups.text
          fontFamily: Style.font.family
        }

        Text {
          width: parent.width
          wrapMode: Text.Wrap
          text: root.panel && root.panel.runtimeReady
            ? (!root.panel.serviceStatusKnown
                ? "Local reuse is available. Checking service discovery."
                : root.panel.serviceReady
                  ? "Local reuse and service discovery are available."
                  : "Local reuse is available. Opt in for service discovery.")
            : "Install a private, per-user runtime. Nothing is installed globally or shared."
          color: Color.popups.text
          opacity: 0.72
          font.family: Style.font.family
          font.pixelSize: Style.font.bodySmall
        }

        Rectangle {
          visible: root.panel && root.panel.runtimeReady && !root.panel.settingsModalOpen
          width: parent.width
          height: root.controlHeight
          radius: Style.cornerRadius
          color: Color.popups.background
          border.color: libraryObjectiveInput.activeFocus ? Color.accent : Color.popups.border
          border.width: 1

          TextInput {
            id: libraryObjectiveInput
            anchors.fill: parent
            anchors.leftMargin: 10
            anchors.rightMargin: 10
            verticalAlignment: TextInput.AlignVCenter
            clip: true
            enabled: !root.commandRunning
            text: root.panel ? root.panel.serviceObjective : ""
            color: Color.popups.text
            font.family: Style.font.family
            font.pixelSize: Style.font.bodySmall
            selectByMouse: true
            onTextEdited: if (root.panel) root.panel.serviceObjective = text

            Text {
              anchors.fill: parent
              verticalAlignment: Text.AlignVCenter
              visible: libraryObjectiveInput.text === ""
              text: "What are you about to make or change?"
              color: Color.popups.text
              opacity: 0.45
              font: libraryObjectiveInput.font
            }
          }
        }

        Button {
          visible: root.panel && !root.panel.runtimeReady
          width: parent.width
          height: root.controlHeight
          text: "Install local runtime"
          bordered: true
          focusable: true
          enabled: !root.commandRunning
          onClicked: if (root.panel) root.panel.installRuntime()
        }

        Row {
          visible: root.panel && root.panel.runtimeReady
          width: parent.width
          spacing: 8

          Button {
            width: 216
            height: root.controlHeight
            text: "Query local Library"
            bordered: true
            focusable: true
            enabled: !root.commandRunning
            onClicked: if (root.panel) root.panel.queryCatalog()
          }

          Button {
            width: 216
            height: root.controlHeight
            text: root.panel && root.panel.settingsModalOpen ? "Close settings" : "Library settings"
            selected: root.panel && root.panel.settingsModalOpen
            bordered: true
            focusable: true
            enabled: !root.commandRunning
            onClicked: if (root.panel) {
              if (root.panel.settingsModalOpen) root.panel.selectSection("library")
              else root.panel.openSettings()
            }
          }
        }

        Text {
          visible: root.panel && root.panel.runtimeReady
          width: parent.width
          wrapMode: Text.Wrap
          text: "Local decisions stay on this machine. Desktop changes still require explicit review and enablement."
          color: Color.popups.text
          opacity: 0.58
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
        }

        BorderSurface {
          visible: root.panel && root.panel.runtimeReady && root.panel.settingsModalOpen
          width: parent.width
          implicitHeight: librarySettingsContent.implicitHeight + 24
          color: Color.popups.background
          borderSpec: Border.flat(Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, 0.46), 1)
          radius: Style.cornerRadius

          Column {
            id: librarySettingsContent
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            spacing: 10

            Text {
              width: parent.width
              text: "DEFAULT SHARING"
              color: Color.popups.text
              font.family: Style.font.family
              font.pixelSize: Style.font.caption
              font.bold: true
              font.letterSpacing: 0.7
            }

            Text {
              width: parent.width
              wrapMode: Text.Wrap
              text: "Choose where newly registered methods should be available. A specific repository or contribution can override this default."
              color: Color.popups.text
              opacity: 0.68
              font.family: Style.font.family
              font.pixelSize: Style.font.caption
            }

            Flow {
              width: parent.width
              spacing: 6

              Repeater {
                model: [
                  { label: "Off", value: "off" },
                  { label: "Local", value: "local" },
                  { label: "Team", value: "circle" },
                  { label: "Organization", value: "organization" },
                  { label: "Public", value: "public" }
                ]

                delegate: Button {
                  required property var modelData
                  width: modelData.value === "organization" ? 128 : 96
                  height: 30
                  text: modelData.label
                  selected: root.panel && root.panel.pendingDefaultDestination === modelData.value
                  bordered: true
                  focusable: true
                  onClicked: if (root.panel) root.panel.pendingDefaultDestination = modelData.value
                }
              }
            }

            Text {
              width: parent.width
              text: "CONTRIBUTION MODE"
              color: Color.popups.text
              font.family: Style.font.family
              font.pixelSize: Style.font.caption
              font.bold: true
              font.letterSpacing: 0.7
            }

            Row {
              width: parent.width
              spacing: 6

              Repeater {
                model: [
                  { label: "Manual", value: "manual" },
                  { label: "Agent-mediated", value: "agent-mediated" },
                  { label: "Automatic", value: "automatic" }
                ]

                delegate: Button {
                  required property var modelData
                  width: (parent.width - parent.spacing * 2) / 3
                  height: 30
                  text: modelData.label
                  selected: root.panel && root.panel.pendingContributionMode === modelData.value
                  bordered: true
                  focusable: true
                  onClicked: if (root.panel) root.panel.pendingContributionMode = modelData.value
                }
              }
            }

            Text {
              width: parent.width
              text: "REUSABLE MATERIAL"
              color: Color.popups.text
              font.family: Style.font.family
              font.pixelSize: Style.font.caption
              font.bold: true
              font.letterSpacing: 0.7
            }

            Row {
              width: parent.width
              spacing: 6

              Button {
                width: (parent.width - parent.spacing) / 2
                height: 30
                text: "Methods only"
                selected: root.panel && root.panel.pendingMaterialPolicy === "methods-only"
                bordered: true
                focusable: true
                onClicked: if (root.panel) root.panel.pendingMaterialPolicy = "methods-only"
              }

              Button {
                width: (parent.width - parent.spacing) / 2
                height: 30
                text: "Methods + exact sources"
                selected: root.panel && root.panel.pendingMaterialPolicy === "methods-and-exact"
                bordered: true
                focusable: true
                onClicked: if (root.panel) root.panel.pendingMaterialPolicy = "methods-and-exact"
              }
            }

            Text {
              visible: root.panel && root.panel.pendingDefaultDestination === "public"
              width: parent.width
              wrapMode: Text.Wrap
              text: root.panel && root.panel.pendingContributionMode === "automatic"
                ? "Automatic + Public is a standing authorization: qualifying methods publish silently after registration. Saving binds that authorization to the verified publication policy; a policy change pauses publication for review."
                : "Saving Public binds this destination to the verified publication policy. The selected contribution mode still controls who initiates registration."
              color: Color.accent
              font.family: Style.font.family
              font.pixelSize: Style.font.caption
            }

            Button {
              visible: root.panel && root.panel.pendingDefaultDestination === "public"
              width: parent.width
              height: 30
              text: "View verified publication policy ↗"
              bordered: true
              focusable: true
              enabled: root.panel && root.panel.publicationPolicyReady && !root.commandRunning
              onClicked: if (root.panel) root.panel.openPublicationPolicy()
            }

            Row {
              width: parent.width
              spacing: 8

              Button {
                width: 208
                height: root.controlHeight
                text: "Cancel"
                bordered: true
                focusable: true
                onClicked: if (root.panel) root.panel.selectSection("library")
              }

              Button {
                width: 208
                height: root.controlHeight
                text: "Save"
                selected: true
                bordered: true
                focusable: true
                enabled: !root.commandRunning
                onClicked: if (root.panel) root.panel.saveSettings()
              }
            }
          }
        }

        PanelSectionHeader {
          visible: root.panel && root.panel.runtimeReady && !root.panel.settingsModalOpen
          width: parent.width
          text: "PUBLIC AND SHARED REUSE"
          foreground: Color.popups.text
          fontFamily: Style.font.family
        }

        Button {
          visible: root.panel && root.panel.runtimeReady && !root.panel.settingsModalOpen
          width: parent.width
          height: root.controlHeight
          text: root.panel && !root.panel.serviceStatusKnown
            ? "Checking service connection"
            : root.panel && root.panel.serviceReady
              ? (root.panel.serviceUsageExceeded ? "View usage and upgrade options" : "Query Limitless Library service")
              : "Connect to Limitless Library service"
          bordered: true
          focusable: true
          enabled: root.panel && root.panel.serviceStatusKnown && !root.commandRunning
          onClicked: if (root.panel) {
            if (!root.panel.serviceReady || root.panel.serviceUsageExceeded) root.panel.connectServiceFromLibrary()
            else root.panel.queryService()
          }
        }

        Button {
          visible: root.panel && root.panel.runtimeReady && !root.panel.settingsModalOpen
            && root.panel.serviceArtifactReviewAvailable
          width: parent.width
          height: root.controlHeight
          text: "Prepare verified plugin review"
          bordered: true
          focusable: true
          enabled: root.panel && root.panel.serviceReady && !root.commandRunning
          onClicked: if (root.panel) root.panel.prepareServiceArtifactReview()
        }

        Button {
          visible: root.panel && root.panel.runtimeReady && !root.panel.settingsModalOpen
            && root.panel.serviceArtifactInstallAvailable
          width: parent.width
          height: root.controlHeight
          text: "Install reviewed plugin disabled"
          bordered: true
          focusable: true
          enabled: root.panel && root.panel.serviceReady && !root.commandRunning
          onClicked: if (root.panel) root.panel.installServiceArtifactDisabled()
        }

        Button {
          visible: root.panel && root.panel.runtimeReady && !root.panel.settingsModalOpen
            && root.panel.serviceArtifactEnableAvailable
          width: parent.width
          height: root.controlHeight
          text: "Enable reviewed plugin"
          bordered: true
          focusable: true
          enabled: root.panel && root.panel.serviceReady && !root.commandRunning
          onClicked: if (root.panel) root.panel.enableServiceArtifact()
        }

        Text {
          visible: root.panel && root.panel.runtimeReady && !root.panel.settingsModalOpen
            && root.panel.serviceSummary !== "No managed-service request has been made."
          width: parent.width
          wrapMode: Text.WrapAnywhere
          text: root.panel ? root.panel.serviceSummary : ""
          color: Color.accent
          opacity: 0.82
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
        }

        PanelSectionHeader {
          visible: root.panel && root.panel.runtimeReady && !root.panel.settingsModalOpen
            && root.panel.draftTotal > 0
          width: parent.width
          text: "REGISTERED METHODS"
          foreground: Color.popups.text
          fontFamily: Style.font.family
        }

        Repeater {
          model: root.panel && !root.panel.settingsModalOpen ? root.panel.draftItems : []

          delegate: BorderSurface {
            id: registeredMethodCard
            required property var modelData
            width: 440
            implicitHeight: registeredMethodContent.implicitHeight + 16
            color: Color.popups.background
            borderSpec: Border.flat(Color.popups.border, 1)
            radius: Style.cornerRadius

            Column {
              id: registeredMethodContent
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              anchors.leftMargin: 10
              anchors.rightMargin: 10
              spacing: 2

              Row {
                width: parent.width
                spacing: 8

                Text {
                  width: 328
                  anchors.verticalCenter: parent.verticalCenter
                  text: String(modelData.title || "Registered method")
                  elide: Text.ElideRight
                  color: Color.popups.text
                  font.family: Style.font.family
                  font.pixelSize: Style.font.bodySmall
                  font.bold: true
                }

                Button {
                  visible: String(modelData.status || "") !== "superseded"
                  width: 82
                  height: 26
                  text: root.panel && root.panel.draftManageRef === String(modelData.draftRef)
                    ? "Close"
                    : "Manage"
                  selected: root.panel && root.panel.draftManageRef === String(modelData.draftRef)
                  bordered: true
                  focusable: true
                  enabled: !root.commandRunning
                  onClicked: if (root.panel) root.panel.toggleDraftManagement(modelData.draftRef)
                }
              }

              Text {
                width: parent.width
                text: String(modelData.status || "pending") + "  ·  "
                  + String(modelData.destination || "local") + "  ·  revision "
                  + String(modelData.revision || 1)
                color: Color.popups.text
                opacity: 0.56
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
              }

              Text {
                visible: root.panel && root.panel.draftManageRef === String(modelData.draftRef)
                width: parent.width
                text: "MOVE AVAILABILITY"
                color: Color.popups.text
                opacity: 0.58
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
                font.bold: true
                font.letterSpacing: 0.7
              }

              Flow {
                visible: root.panel && root.panel.draftManageRef === String(modelData.draftRef)
                width: parent.width
                spacing: 6

                Repeater {
                  model: [
                    { label: "Local", value: "local" },
                    { label: "Team", value: "circle" },
                    { label: "Organization", value: "organization" },
                    { label: "Public", value: "public" }
                  ]

                  delegate: Button {
                    required property var modelData
                    width: modelData.value === "organization" ? 128 : 88
                    height: 28
                    text: modelData.label
                    selected: String(registeredMethodCard.modelData.destination || "local") === modelData.value
                    bordered: true
                    focusable: true
                    enabled: !root.commandRunning && (modelData.value !== "public"
                      || root.panel && root.panel.serviceReady && root.panel.publicationPolicyReady)
                    onClicked: if (root.panel)
                      root.panel.transitionDraft(registeredMethodCard.modelData.draftRef, modelData.value)
                  }
                }
              }

              Text {
                visible: root.panel && root.panel.draftManageRef === String(modelData.draftRef)
                width: parent.width
                wrapMode: Text.Wrap
                text: "Public withdrawals preserve provenance. A withdrawn release must be revised before publication again."
                color: Color.popups.text
                opacity: 0.52
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
              }
            }
          }
        }
      }

      // Agent connections ---------------------------------------------------
      Column {
        visible: root.panel && root.panel.runtimeReady && root.panel.activeSection === "agents"
        width: parent.width
        spacing: 12

        PanelSectionHeader {
          width: parent.width
          text: "AGENT CONNECTION"
          foreground: Color.popups.text
          fontFamily: Style.font.family
        }

        Text {
          width: parent.width
          wrapMode: Text.Wrap
          text: root.panel ? root.panel.agentSummary : ""
          color: Color.popups.text
          opacity: 0.75
          font.family: Style.font.family
          font.pixelSize: Style.font.bodySmall
        }

        Row {
          width: parent.width
          spacing: 8

          Button {
            width: 216
            height: root.controlHeight
            text: root.panel && root.panel.defaultAgent !== ""
              ? "Connect " + root.panel.agentLabel(root.panel.defaultAgent)
              : "Choose Omarchy default"
            bordered: true
            focusable: true
            enabled: root.panel && root.panel.defaultAgent !== "" && !root.commandRunning
            onClicked: if (root.panel) root.panel.reconcileAgents()
          }

          Button {
            width: 216
            height: root.controlHeight
            text: "Refresh status"
            bordered: true
            focusable: true
            enabled: !root.commandRunning
            onClicked: if (root.panel) root.panel.refreshAgentStatus()
          }
        }

        Button {
          width: parent.width
          height: root.controlHeight
          text: root.panel && root.panel.agentOptionsExpanded
            ? "Hide additional agents"
            : "Optional additional agents"
          bordered: true
          focusable: true
          enabled: !root.commandRunning
          onClicked: if (root.panel) root.panel.agentOptionsExpanded = !root.panel.agentOptionsExpanded
        }

        Flow {
          visible: root.panel && root.panel.agentOptionsExpanded
          width: parent.width
          spacing: 8

          Repeater {
            model: root.panel ? root.panel.agentOptions : []

            delegate: Button {
              required property var modelData
              visible: root.panel && String(modelData.id) !== root.panel.defaultAgent
              height: Math.max(30, Style.spacing.controlHeight - 4)
              text: root.panel && root.panel.hasAdditionalAgent(modelData.id)
                ? "✓ " + String(modelData.label)
                : String(modelData.label)
              selected: root.panel && root.panel.hasAdditionalAgent(modelData.id)
              bordered: true
              focusable: true
              enabled: !root.commandRunning
              onClicked: if (root.panel) root.panel.toggleAdditionalAgent(modelData.id)
            }
          }
        }

        Button {
          visible: root.panel && root.panel.agentOptionsExpanded
            && root.panel.additionalAgentIds.length > 0
          width: parent.width
          height: root.controlHeight
          text: "Apply selected agent connections"
          bordered: true
          focusable: true
          enabled: !root.commandRunning
          onClicked: if (root.panel) root.panel.reconcileAgents()
        }

        Text {
          visible: root.panel && root.panel.agentOptionsExpanded
            && root.panel.agentReportNeeded && root.panel.agentReportPath !== ""
          width: parent.width
          wrapMode: Text.WrapAnywhere
          text: root.panel ? "Connection report: " + root.panel.agentReportPath : ""
          color: Color.popups.text
          opacity: 0.5
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
        }

        Button {
          visible: root.panel && root.panel.agentOptionsExpanded
          width: parent.width
          height: root.controlHeight
          text: "Disconnect plugin-owned agent connections"
          bordered: true
          focusable: true
          enabled: !root.commandRunning
          onClicked: if (root.panel) root.panel.disconnectAgents()
        }

        Text {
          width: parent.width
          wrapMode: Text.Wrap
          text: "Your Omarchy default is the normal path. Add another agent only when you want Limitless available there too."
          color: Color.popups.text
          opacity: 0.58
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
        }
      }

      // About ---------------------------------------------------------------
      Column {
        visible: root.panel && root.panel.activeSection === "about"
        width: parent.width
        spacing: 12

        BorderSurface {
          width: parent.width
          implicitHeight: 70
          color: Color.popups.background
          borderSpec: Border.flat(Color.popups.border, 1)
          radius: Style.cornerRadius

          Row {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            spacing: 10

            Loader {
              width: 42
              height: 42
              sourceComponent: limitlessLibraryLogoIcon
            }

            Column {
              width: 312
              anchors.verticalCenter: parent.verticalCenter
              spacing: 2

              Text {
                width: parent.width
                text: "Limitless Library"
                horizontalAlignment: Text.AlignHCenter
                color: Color.popups.text
                font.family: Style.font.family
                font.pixelSize: Style.font.body
                font.bold: true
              }

              Text {
                width: parent.width
                text: "a Univeracity project"
                horizontalAlignment: Text.AlignHCenter
                color: Color.popups.text
                opacity: 0.62
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
              }
            }

            Loader {
              width: 42
              height: 42
              sourceComponent: univeracityIcon
            }
          }
        }

        PanelSectionHeader {
          width: parent.width
          text: "WELCOME TO THE LIMITLESS LIBRARY"
          foreground: Color.popups.text
          fontFamily: Style.font.family
        }

        Text {
          width: parent.width
          wrapMode: Text.Wrap
          text: "Limitless emerged after seeing agents rebuild good work across repositories, sessions, and teams. Safe reuse requires more than search: trusted checks must ensure prior work is allowed, compatible, unchanged, and actually adopted."
          color: Color.popups.text
          opacity: 0.76
          font.family: Style.font.family
          font.pixelSize: Style.font.bodySmall
        }

        PanelSectionHeader {
          width: parent.width
          text: "THE LONG VIEW"
          foreground: Color.popups.text
          fontFamily: Style.font.family
        }

        Text {
          width: parent.width
          wrapMode: Text.Wrap
          text: "As the Limitless Library grows, valuable work compounds across people, tools, and environments. Limitless keeps local control intact while opening a path to permissioned public and shared reuse. Omarchy is where this concept naturally fits: a system built to be owned and reshaped by its user and its community."
          color: Color.popups.text
          opacity: 0.76
          font.family: Style.font.family
          font.pixelSize: Style.font.bodySmall
        }

        BorderSurface {
          width: parent.width
          implicitHeight: aboutQuip.implicitHeight + 24
          color: Color.popups.background
          borderSpec: Border.flat(Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, 0.42), 1)
          radius: Style.cornerRadius

          Text {
            id: aboutQuip
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            text: "Omarchy: the revolution will be customized."
            horizontalAlignment: Text.AlignHCenter
            color: Color.accent
            wrapMode: Text.Wrap
            font.family: Style.font.family
            font.pixelSize: Style.font.body
            font.bold: true
          }
        }

        PanelSectionHeader {
          width: parent.width
          text: "OFFICIAL LINKS"
          foreground: Color.popups.text
          fontFamily: Style.font.family
        }

        Row {
          width: parent.width
          spacing: 8

          Button {
            width: 216
            height: root.controlHeight
            text: "Limitless Library ↗"
            bordered: true
            focusable: true
            onClicked: if (root.panel) root.panel.openOfficialUrl("https://limitlesslibrary.com")
          }

          Button {
            width: 216
            height: root.controlHeight
            text: "Univeracity ↗"
            bordered: true
            focusable: true
            onClicked: if (root.panel) root.panel.openOfficialUrl("https://univeracity.com")
          }
        }

        Row {
          width: parent.width
          spacing: 8

          Button {
            width: 216
            height: root.controlHeight
            text: root.panel && root.panel.runtimeReady ? "Update runtime" : "Install runtime"
            bordered: true
            focusable: true
            enabled: !root.commandRunning
            onClicked: if (root.panel) root.panel.installRuntime()
          }

          Button {
            width: 216
            height: root.controlHeight
            text: "Source on GitHub ↗"
            bordered: true
            focusable: true
            onClicked: if (root.panel) root.panel.openOfficialUrl("https://github.com/Univeracity/limitless-omarchy")
          }
        }

        Text {
          width: parent.width
          horizontalAlignment: Text.AlignHCenter
          text: "© 2026 Limitless Library · Apache-2.0"
          color: Color.popups.text
          opacity: 0.54
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
        }
      }

      // Private aggregate activity ------------------------------------------
      Column {
        visible: root.panel && root.panel.runtimeReady && root.panel.activeSection === "stats"
        width: parent.width
        spacing: 12

        PanelSectionHeader {
          width: parent.width
          text: "PLUGIN-OBSERVED ACTIVITY"
          foreground: Color.popups.text
          fontFamily: Style.font.family
        }

        Grid {
          width: parent.width
          columns: 2
          columnSpacing: 8
          rowSpacing: 8

          StatTile {
            label: "Queries checked"
            value: root.panel ? String(root.panel.statsQueries) : "0"
            loading: root.panel && root.panel.commandRunning && root.panel.operation === "stats"
          }

          StatTile {
            label: "Useful returns"
            value: root.panel
              ? String(root.panel.statsExactComponents + root.panel.statsSourceFreeMethods)
              : "0"
            highlighted: root.panel
              && root.panel.statsExactComponents + root.panel.statsSourceFreeMethods > 0
            loading: root.panel && root.panel.commandRunning && root.panel.operation === "stats"
          }

          StatTile {
            label: "Omarchy-specific queries"
            value: root.panel ? String(root.panel.statsLocalQueries + root.panel.statsServiceQueries) : "0"
            loading: root.panel && root.panel.commandRunning && root.panel.operation === "stats"
          }

          StatTile {
            label: "General queries"
            value: root.panel ? String(root.panel.statsGeneralQueries) : "0"
            loading: root.panel && root.panel.commandRunning && root.panel.operation === "stats"
          }

          StatTile {
            label: "Safe abstentions"
            value: root.panel ? String(root.panel.statsAbstentions) : "0"
            loading: root.panel && root.panel.commandRunning && root.panel.operation === "stats"
          }

          StatTile {
            label: "Verified adoptions"
            value: root.panel ? String(root.panel.statsAdoptions) : "0"
            highlighted: root.panel && root.panel.statsAdoptions > 0
            loading: root.panel && root.panel.commandRunning && root.panel.operation === "stats"
          }
        }

        BorderSurface {
          width: parent.width
          implicitHeight: activityBreakdown.implicitHeight + 20
          color: Color.popups.background
          borderSpec: Border.flat(Color.popups.border, 1)
          radius: Style.cornerRadius

          Column {
            id: activityBreakdown
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.leftMargin: 10
            anchors.rightMargin: 10
            spacing: 4

            Row {
              width: parent.width
              spacing: 8

              InlineMetric {
                width: 78
                label: "Local"
                value: root.panel ? String(root.panel.statsLocalQueries) : "0"
                loading: root.panel && root.panel.commandRunning && root.panel.operation === "stats"
              }
              InlineMetric {
                width: 78
                label: "Service"
                value: root.panel ? String(root.panel.statsServiceQueries) : "0"
                loading: root.panel && root.panel.commandRunning && root.panel.operation === "stats"
              }
              InlineMetric {
                width: 78
                label: "General"
                value: root.panel ? String(root.panel.statsGeneralQueries) : "0"
                loading: root.panel && root.panel.commandRunning && root.panel.operation === "stats"
              }
              InlineMetric {
                width: 78
                label: "Exact"
                value: root.panel ? String(root.panel.statsExactComponents) : "0"
                loading: root.panel && root.panel.commandRunning && root.panel.operation === "stats"
              }
              InlineMetric {
                width: 78
                label: "Methods"
                value: root.panel ? String(root.panel.statsSourceFreeMethods) : "0"
                loading: root.panel && root.panel.commandRunning && root.panel.operation === "stats"
              }
            }

            Row {
              width: parent.width
              spacing: 8

              InlineMetric {
                width: 136
                label: "Agents"
                value: root.panel ? String(root.panel.statsAgentsConnected) : "0"
                loading: root.panel && root.panel.commandRunning && root.panel.operation === "stats"
              }
              InlineMetric {
                width: 136
                label: "Attention"
                value: root.panel ? String(root.panel.statsAgentsAttention) : "0"
                loading: root.panel && root.panel.commandRunning && root.panel.operation === "stats"
              }
              InlineMetric {
                width: 136
                label: "Drafts"
                value: root.panel ? String(root.panel.statsDrafts) : "0"
                loading: root.panel && root.panel.commandRunning && root.panel.operation === "stats"
              }
            }

            Row {
              width: parent.width
              spacing: 8

              InlineMetric {
                width: 78
                label: "Reviews"
                value: root.panel ? String(root.panel.statsReviews) : "0"
                loading: root.panel && root.panel.commandRunning && root.panel.operation === "stats"
              }
              InlineMetric {
                width: 78
                label: "Installs"
                value: root.panel ? String(root.panel.statsInstalls) : "0"
                loading: root.panel && root.panel.commandRunning && root.panel.operation === "stats"
              }
              InlineMetric {
                width: 78
                label: "Adopted"
                value: root.panel ? String(root.panel.statsAdoptions) : "0"
                loading: root.panel && root.panel.commandRunning && root.panel.operation === "stats"
              }
              InlineMetric {
                width: 78
                label: "Public"
                value: root.panel ? String(root.panel.statsPublications) : "0"
                loading: root.panel && root.panel.commandRunning && root.panel.operation === "stats"
              }
              InlineMetric {
                width: 78
                label: "Withdrawn"
                value: root.panel ? String(root.panel.statsWithdrawals) : "0"
                loading: root.panel && root.panel.commandRunning && root.panel.operation === "stats"
              }
            }

            Text {
              width: parent.width
              text: root.panel && root.panel.statsServiceConnected
                ? "Limitless service connected"
                : "Local-only mode"
              color: Color.popups.text
              opacity: 0.64
              font.family: Style.font.family
              font.pixelSize: Style.font.caption
            }
          }
        }

        Text {
          width: parent.width
          wrapMode: Text.Wrap
          text: {
            if (!root.panel || !root.panel.statsAvailable)
              return "The scorekeeper misplaced its pencil. Other Limitless operations still work."
            var useful = root.panel.statsExactComponents + root.panel.statsSourceFreeMethods
            if (root.panel.statsAdoptions > 0)
              return "A wheel was left peacefully un-reinvented."
            if (useful > 0)
              return "Looks like reuse showed up to work. Nice."
            if (root.panel.statsAbstentions > 0)
              return "Fresh starts: justified, not improvised."
            return "The counters are stretching. Give them a query."
          }
          color: Color.accent
          font.family: Style.font.family
          font.pixelSize: Style.font.bodySmall
          font.bold: true
        }

        Button {
          width: parent.width
          height: root.controlHeight
          text: "Refresh activity"
          bordered: true
          focusable: true
          enabled: !root.commandRunning
          onClicked: if (root.panel) root.panel.refreshStats()
        }

        Text {
          width: parent.width
          wrapMode: Text.Wrap
          text: "Only aggregate counters are stored locally—never objectives, prompts, paths, IDs, or result contents. Omarchy and opt-in general-provider activity remain separate in the totals above."
          color: Color.popups.text
          opacity: 0.58
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
        }
      }

      // Managed service -----------------------------------------------------
      Column {
        visible: root.panel && root.panel.runtimeReady && root.panel.activeSection === "service"
        width: parent.width
        spacing: 12

        PanelSectionHeader {
          width: parent.width
          text: "LIMITLESS LIBRARY SERVICE"
          foreground: Color.popups.text
          fontFamily: Style.font.family
        }

        Text {
          width: parent.width
          wrapMode: Text.Wrap
          text: root.panel && root.panel.serviceUsageExceeded
            ? "The public Library remains connected. Local reuse is still available while free service usage resets."
            : root.panel && !root.panel.serviceStatusKnown
              ? "Checking the saved service connection. Local reuse remains available."
              : root.panel && root.panel.serviceReady
                ? "Anonymous service access is active. Accounts add persistent history, teams, organizations, and higher usage."
                : "Connect for anonymous public discovery. No account, profile, or API key is required."
          color: Color.popups.text
          opacity: 0.75
          font.family: Style.font.family
          font.pixelSize: Style.font.bodySmall
        }

        Button {
          visible: root.panel && !root.panel.serviceReady
          width: parent.width
          height: root.controlHeight
          text: root.panel && root.panel.serviceStatusKnown
            ? "Connect to Limitless Library service"
            : "Checking service connection"
          bordered: true
          focusable: true
          enabled: root.panel && root.panel.serviceStatusKnown && !root.commandRunning
          onClicked: if (root.panel) root.panel.activateService()
        }

        BorderSurface {
          visible: root.panel && root.panel.serviceUsageExceeded
          width: parent.width
          implicitHeight: usageLimitContent.implicitHeight + 20
          color: Color.popups.background
          borderSpec: Border.flat(Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, 0.38), 1)
          radius: Style.cornerRadius

          Column {
            id: usageLimitContent
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.leftMargin: 10
            anchors.rightMargin: 10
            spacing: 8

            Text {
              width: parent.width
              wrapMode: Text.Wrap
              text: root.panel ? root.panel.serviceSummary : ""
              color: Color.popups.text
              font.family: Style.font.family
              font.pixelSize: Style.font.bodySmall
              font.bold: true
            }

            Button {
              width: parent.width
              height: root.controlHeight
              text: "Upgrade or request more usage ↗"
              bordered: true
              focusable: true
              enabled: !root.commandRunning
              onClicked: if (root.panel) root.panel.openUsageUpgrade()
            }
          }
        }

        BorderSurface {
          visible: root.panel && root.panel.serviceReady
          width: parent.width
          implicitHeight: serviceIdentityContent.implicitHeight + 20
          color: Color.popups.background
          borderSpec: Border.flat(Color.popups.border, 1)
          radius: Style.cornerRadius

          Column {
            id: serviceIdentityContent
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.leftMargin: 10
            anchors.rightMargin: 10
            spacing: 4

            Text {
              width: parent.width
              text: "ANONYMOUS INSTALLATION"
              color: Color.popups.text
              font.family: Style.font.family
              font.pixelSize: Style.font.caption
              font.bold: true
              font.letterSpacing: 0.7
            }

            Text {
              width: parent.width
              wrapMode: Text.Wrap
              text: "Public discovery is connected. History stays on this device unless an account is used to persist it with the service."
              color: Color.popups.text
              opacity: 0.68
              font.family: Style.font.family
              font.pixelSize: Style.font.bodySmall
            }
          }
        }

        PanelSectionHeader {
          visible: root.panel && root.panel.serviceReady
          width: parent.width
          text: "SHARING"
          foreground: Color.popups.text
          fontFamily: Style.font.family
        }

        Text {
          visible: root.panel && root.panel.serviceReady
          width: parent.width
          wrapMode: Text.Wrap
          text: {
            if (!root.panel) return ""
            var destination = root.panel.settingsDefaultDestination
            var mode = root.panel.settingsContributionMode
            if (destination === "off") return "Contribution is off. Existing local work remains available."
            if (destination === "circle" || destination === "organization")
              return "New methods target " + (destination === "circle" ? "a team" : "an organization")
                + ". Until an account supplies that scope, they remain safely queued on this device."
            if (destination === "public" && mode === "automatic")
              return "Qualifying methods are registered silently and queued for automatic public sharing under the saved policy authorization."
            return "New methods default to " + destination + " with " + mode + " contribution."
          }
          color: Color.popups.text
          opacity: 0.72
          font.family: Style.font.family
          font.pixelSize: Style.font.bodySmall
        }

        Row {
          visible: root.panel && root.panel.serviceReady
          width: parent.width
          spacing: 8

          Button {
            width: 216
            height: root.controlHeight
            text: "Library settings"
            bordered: true
            focusable: true
            enabled: !root.commandRunning
            onClicked: if (root.panel) root.panel.openLibrarySettings()
          }

          Button {
            width: 216
            height: root.controlHeight
            text: "Upgrade or create account ↗"
            bordered: true
            focusable: true
            enabled: !root.commandRunning
            onClicked: if (root.panel) root.panel.openUsageUpgrade()
          }
        }

        Text {
          visible: root.panel && root.panel.serviceReady && root.panel.draftTotal > 0
          width: parent.width
          wrapMode: Text.Wrap
          text: root.panel
            ? String(root.panel.draftPending) + " current method"
              + (root.panel.draftPending === 1 ? "" : "s") + " · "
              + String(root.panel.draftTotal) + " total revision"
              + (root.panel.draftTotal === 1 ? "" : "s")
            : ""
          color: Color.accent
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
        }

        Button {
          width: parent.width
          height: root.controlHeight
          text: root.panel && root.panel.serviceDetailsExpanded
            ? "Hide connection details"
            : "Connection and trust details"
          bordered: true
          focusable: true
          enabled: !root.commandRunning
          onClicked: if (root.panel) root.panel.serviceDetailsExpanded = !root.panel.serviceDetailsExpanded
        }

        Text {
          visible: root.panel && root.panel.serviceDetailsExpanded
          width: parent.width
          wrapMode: Text.Wrap
          text: "Connection verifies the release-pinned service identity, trust root, and policy, then creates a private on-device identity. No account, profile file, or API key is required. Queries send only the objective and minimal receiver context you approve."
          color: Color.popups.text
          opacity: 0.68
          font.family: Style.font.family
          font.pixelSize: Style.font.bodySmall
        }

        Rectangle {
          visible: root.panel && root.panel.serviceDetailsExpanded
          width: parent.width
          height: root.controlHeight
          radius: Style.cornerRadius
          color: Color.popups.background
          border.color: omarchyReleaseInput.activeFocus ? Color.accent : Color.popups.border
          border.width: 1

          TextInput {
            id: omarchyReleaseInput
            anchors.fill: parent
            anchors.leftMargin: 10
            anchors.rightMargin: 10
            verticalAlignment: TextInput.AlignVCenter
            clip: true
            text: root.panel ? root.panel.omarchyRelease : ""
            color: Color.popups.text
            font.family: Style.font.family
            font.pixelSize: Style.font.bodySmall
            selectByMouse: true
            onTextEdited: if (root.panel) root.panel.omarchyRelease = text

            Text {
              anchors.fill: parent
              verticalAlignment: Text.AlignVCenter
              visible: omarchyReleaseInput.text === ""
              text: "Omarchy release (optional)"
              color: Color.popups.text
              opacity: 0.45
              font: omarchyReleaseInput.font
            }
          }
        }

        Button {
          visible: root.panel && root.panel.serviceDetailsExpanded
          width: parent.width
          height: root.controlHeight
          text: "Inspect trust boundary"
          bordered: true
          focusable: true
          enabled: root.panel && root.panel.serviceReady && !root.commandRunning
          onClicked: if (root.panel) root.panel.inspectService()
        }

      }
    }
  }
}
