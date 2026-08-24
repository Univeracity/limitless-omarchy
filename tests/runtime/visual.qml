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
    property string activeSection: "library"
    property bool settingsModalOpen: false
    property bool settingsLoaded: true
    property string settingsDefaultDestination: "local"
    property string settingsContributionMode: "agent-mediated"
    property string settingsMaterialPolicy: "methods-only"
    property string settingsPublicPolicyDigest: ""
    property string pendingDefaultDestination: "local"
    property string pendingContributionMode: "agent-mediated"
    property string pendingMaterialPolicy: "methods-only"
    property var draftItems: [
      {
        draftRef: "draft:01M0R7NZZB19KZMFS1X0HEK3DH",
        title: "Lock-safe live plugin updates",
        revision: 1,
        destination: "local",
        status: "local"
      },
      {
        draftRef: "draft:01M0R7NZZB19KZMFS1X0HEK3DJ",
        title: "Stable Wi-Fi credential entry",
        revision: 2,
        destination: "public",
        status: "published"
      }
    ]
    property int draftTotal: 2
    property int draftPending: 2
    property string draftManageRef: ""
    property bool agentOptionsExpanded: false
    property bool serviceDetailsExpanded: false
    property bool serviceExpanded: false
    property bool serviceReady: false
    property bool serviceStatusKnown: true
    property bool serviceUsageExceeded: false
    property string serviceUsageResetsAt: ""
    property string serviceUpgradeUrl: "https://limitlesslibrary.com/#contact"
    property bool serviceArtifactStageAvailable: true
    property bool serviceArtifactReviewAvailable: true
    property bool serviceArtifactInstallAvailable: false
    property bool serviceArtifactEnableAvailable: false
    property bool publicationPolicyReady: true
    property string defaultAgent: "codex"
    property var additionalAgentIds: ["claude"]
    property var agentOptions: [
      { id: "agy", label: "Antigravity" },
      { id: "claude", label: "Claude Code" },
      { id: "codex", label: "Codex" },
      { id: "copilot", label: "GitHub Copilot" },
      { id: "crush", label: "Crush" },
      { id: "grok", label: "Grok" },
      { id: "omp", label: "Oh My Pi" },
      { id: "opencode", label: "OpenCode" },
      { id: "pi", label: "Pi" }
    ]
    property string agentSummary: "Default: Codex · local MCP connected."
    property string agentReportPath: "/home/user/.local/share/limitless-omarchy/agent-connection/connection-report.json"
    property bool agentReportNeeded: false
    property bool statsAvailable: true
    property int statsQueries: 24
    property int statsLocalQueries: 12
    property int statsServiceQueries: 7
    property int statsGeneralQueries: 5
    property int statsExactComponents: 3
    property int statsSourceFreeMethods: 8
    property int statsAbstentions: 13
    property int statsReviews: 3
    property int statsInstalls: 2
    property int statsAdoptions: 2
    property int statsPublications: 1
    property int statsWithdrawals: 0
    property int statsDrafts: 2
    property int statsAgentsConnected: 2
    property int statsAgentsAttention: 0
    property bool statsServiceConnected: true
    property string headline: "Local Library ready"
    property string detail: "Local reuse is available. Opt in for service discovery."
    property string selectionReference: ""
    property string errorText: ""
    property string operation: ""
    property string serviceObjective: "Find a recent customization that improves workspace focus"
    property string omarchyRelease: "2026.08"
    property string serviceSummary: "Pinned service · private · local-only · accepted policy"
    property string serviceArtifactHandoffStatePath: "/home/user/.local/state/limitless-omarchy/handoff.json"
    property string serviceArtifactStagedPath: ""
    property string serviceArtifactReviewPath: ""
    property string serviceArtifactInstallationStatePath: ""
    property string serviceArtifactAdoptionReceiptPath: ""
    property string publicationPolicyUrl: "https://limitlesslibrary.com/publication-policy"
    property string publicationPolicyDigest: "sha256:3333333333333333333333333333333333333333333333333333333333333333"
    property string publicationPolicySummary: "publication-2026-08 · sha256:3333333333333333333333333333333333333333333333333333333333333333"

    function installRuntime() {}
    function selectSection(section) {
      settingsModalOpen = false
      activeSection = String(section)
    }
    function openSettings() { settingsModalOpen = true }
    function saveSettings() { settingsModalOpen = false }
    function openLibrarySettings() { activeSection = "library"; settingsModalOpen = true }
    function connectServiceFromLibrary() { activeSection = "service" }
    function toggleDraftManagement(draftRef) {
      draftManageRef = draftManageRef === String(draftRef) ? "" : String(draftRef)
    }
    function transitionDraft(draftRef, destination) {}
    function agentLabel(agentId) {
      for (var index = 0; index < agentOptions.length; index += 1) {
        if (String(agentOptions[index].id) === String(agentId)) return String(agentOptions[index].label)
      }
      return String(agentId)
    }
    function hasAdditionalAgent(agentId) { return additionalAgentIds.indexOf(String(agentId)) >= 0 }
    function toggleAdditionalAgent(agentId) {}
    function refreshAgentStatus() {}
    function reconcileAgents() {}
    function disconnectAgents() {}
    function refreshStats() {}
    function queryCatalog() {}
    function activateService() {}
    function inspectService() {}
    function queryService() {}
    function stageServiceArtifact() {}
    function prepareServiceArtifactReview() {}
    function installServiceArtifactDisabled() {}
    function enableServiceArtifact() {}
    function openPublicationPolicy() {}
    function openOfficialUrl(url) {}
    function openUsageUpgrade() {}
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
    id: previewTimer
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
        root.previewSaved = result.saveToFile(root.outputDirectory + "/preview.png")
        root.panelState.activeSection = "agents"
        root.panelState.agentOptionsExpanded = false
        contents.item.scrollToTop()
        agentTimer.start()
      }, Qt.size(480, 680))
    }
  }

  property bool previewSaved: false
  property bool agentSaved: false
  property bool statsSaved: false
  property bool aboutSaved: false
  property bool topSaved: false
  property bool quotaSaved: false

  Timer {
    id: agentTimer
    interval: 250
    repeat: false
    onTriggered: {
      root.panelState.agentOptionsExpanded = true
      contents.item.scrollToTop()
      agentCaptureTimer.start()
    }
  }

  Timer {
    id: agentCaptureTimer
    interval: 250
    repeat: false
    onTriggered: {
      contents.item.grabToImage(function(result) {
        root.agentSaved = result.saveToFile(root.outputDirectory + "/agents.png")
        root.panelState.activeSection = "stats"
        contents.item.scrollToTop()
        statsTimer.start()
      }, Qt.size(480, 680))
    }
  }

  Timer {
    id: statsTimer
    interval: 250
    repeat: false
    onTriggered: {
      contents.item.scrollToTop()
      statsCaptureTimer.start()
    }
  }

  Timer {
    id: statsCaptureTimer
    interval: 150
    repeat: false
    onTriggered: {
      contents.item.grabToImage(function(result) {
        root.statsSaved = result.saveToFile(root.outputDirectory + "/stats.png")
        root.panelState.activeSection = "about"
        contents.item.scrollToTop()
        aboutTimer.start()
      }, Qt.size(480, 680))
    }
  }

  Timer {
    id: aboutTimer
    interval: 250
    repeat: false
    onTriggered: {
      contents.item.grabToImage(function(result) {
        root.aboutSaved = result.saveToFile(root.outputDirectory + "/about.png")
        root.panelState.activeSection = "service"
        root.panelState.serviceExpanded = true
        root.panelState.serviceReady = true
        root.panelState.agentOptionsExpanded = false
        contents.item.scrollToTop()
        topTimer.start()
      }, Qt.size(480, 680))
    }
  }

  Timer {
    id: topTimer
    interval: 250
    repeat: false
    onTriggered: {
      contents.item.scrollToTop()
      serviceCaptureTimer.start()
    }
  }

  Timer {
    id: serviceCaptureTimer
    interval: 100
    repeat: false
    onTriggered: {
      contents.item.grabToImage(function(result) {
        var topSaved = result.saveToFile(root.outputDirectory + "/service-top.png")
        root.topSaved = topSaved
        root.panelState.serviceUsageExceeded = true
        root.panelState.serviceUsageResetsAt = "2026-08-24T00:00:00Z"
        root.panelState.serviceSummary = "Free usage exceeded. Resets: Aug 24, 2026 · 12:00 AM"
        root.panelState.serviceArtifactReviewAvailable = false
        contents.item.scrollToTop()
        quotaTimer.start()
      }, Qt.size(480, 680))
    }
  }

  Timer {
    id: quotaTimer
    interval: 250
    repeat: false
    onTriggered: {
      contents.item.grabToImage(function(result) {
        root.quotaSaved = result.saveToFile(root.outputDirectory + "/quota.png")
        root.panelState.serviceUsageExceeded = false
        root.panelState.serviceSummary = "Pinned service · private · local-only · accepted policy"
        root.panelState.activeSection = "library"
        root.panelState.settingsModalOpen = true
        var scroll = contents.item.children.length > 0 ? contents.item.children[0] : null
        if (scroll && scroll.contentY !== undefined)
          scroll.contentY = Math.max(0, scroll.contentHeight - scroll.height)
        bottomTimer.start()
      }, Qt.size(480, 680))
    }
  }

  Timer {
    id: bottomTimer
    interval: 250
    repeat: false
    onTriggered: {
      contents.item.grabToImage(function(result) {
        var bottomSaved = result.saveToFile(root.outputDirectory + "/library-settings.png")
        resultFile.setText(JSON.stringify({
          ok: root.previewSaved && root.agentSaved && root.statsSaved && root.aboutSaved
            && root.topSaved && root.quotaSaved && bottomSaved,
          previewSaved: root.previewSaved,
          agentSaved: root.agentSaved,
          statsSaved: root.statsSaved,
          aboutSaved: root.aboutSaved,
          topSaved: root.topSaved,
          quotaSaved: root.quotaSaved,
          bottomSaved: bottomSaved
        }))
        Qt.quit()
      }, Qt.size(480, 680))
    }
  }
}
