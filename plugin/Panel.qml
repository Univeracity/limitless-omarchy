import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons
import qs.Ui
import "." as Local

// Standalone Quattro panel. It owns local setup and use. Managed discovery is
// a separate explicit action and never changes the local-only default.
Item {
  id: root

  property var shell: null
  property var manifest: null
  property bool opened: false
  property string catalogPath: ""
  property string serviceObjective: ""
  property string omarchyRelease: ""
  property bool serviceExpanded: false
  property bool serviceReady: false
  property string serviceSummary: "No managed-service request has been made."
  property string serviceArtifactHandoffStatePath: ""
  property string serviceArtifactStagedPath: ""
  property bool serviceArtifactStageAvailable: false
  property bool publicationExpanded: false
  property string publicationDraftPath: ""
  property string publicationStatePath: ""
  property bool publicationPolicyAccepted: false
  property bool publicationPolicyReady: false
  property string publicationPolicyUrl: ""
  property string publicationPolicyDigest: ""
  property string publicationPolicySummary: "Inspect the trust boundary to load the current public publication policy."
  property bool publicationWithdrawalArmed: false
  property string publicationSummary: "No public contribution has been submitted."
  property string publicationOperation: ""
  property bool runtimeReady: false
  property string headline: "Set up Limitless Library"
  property string detail: "Create an isolated local runtime to begin. Nothing will be shared."
  property string disposition: "status"
  property string selectionReference: ""
  property string errorText: ""
  property string commandOutput: ""
  property string commandError: ""
  property string operation: ""
  property string pendingInput: ""
  readonly property string pluginRoot: manifest && manifest.__sourceDir
    ? String(manifest.__sourceDir) : ""
  readonly property bool commandRunning: command.running

  function open(payloadJson) {
    var payload = {}
    try { payload = JSON.parse(payloadJson || "{}") || {} } catch (e) {}
    if (payload.catalogPath !== undefined) catalogPath = String(payload.catalogPath)
    if (payload.omarchyRelease !== undefined) omarchyRelease = String(payload.omarchyRelease)
    serviceReady = false
    serviceSummary = "No managed-service request has been made."
    serviceArtifactHandoffStatePath = ""
    serviceArtifactStagedPath = ""
    serviceArtifactStageAvailable = false
    publicationPolicyAccepted = false
    publicationPolicyReady = false
    publicationPolicyUrl = ""
    publicationPolicyDigest = ""
    publicationWithdrawalArmed = false
    opened = true
    refresh()
    Qt.callLater(function() { if (opened) keyCatcher.forceActiveFocus() })
  }

  function close() {
    opened = false
    serviceObjective = ""
    publicationPolicyAccepted = false
    publicationWithdrawalArmed = false
    pendingInput = ""
    if (command.running) command.running = false
  }

  function dismiss() {
    if (shell && typeof shell.hide === "function")
      shell.hide((manifest && manifest.id) || "univeracity.limitless-library")
    else close()
  }

  function refresh() {
    runRuntime("status", [])
  }

  function installRuntime() {
    runRuntime("setup", [])
  }

  function queryCatalog() {
    if (catalogPath.trim() === "") {
      errorText = "Choose a readable local catalog before querying it."
      return
    }
    runRuntime("query", ["--catalog", catalogPath.trim()])
  }

  function queryExample() {
    runRuntime("query-demo", [])
  }

  function activateService() {
    runRuntime("service-activate", [])
  }

  function inspectService() {
    runRuntime("service-inspect", [])
  }

  function queryService() {
    if (serviceObjective.trim() === "") {
      errorText = "Describe the customization to search for before sending a managed query."
      return
    }
    var arguments = []
    if (omarchyRelease.trim() !== "") arguments = arguments.concat(["--omarchy-release", omarchyRelease.trim()])
    var input = JSON.stringify({
      schemaVersion: "limitless.omarchy-service-query-input/0.1",
      objective: serviceObjective.trim(),
      accessToken: null
    })
    runRuntime("service-query", arguments, input)
  }

  function stageServiceArtifact() {
    if (!serviceArtifactStageAvailable || !serviceArtifactHandoffStatePath.startsWith("/")) {
      errorText = "No locally bound exact-artifact continuation is available."
      return
    }
    var input = JSON.stringify({
      schemaVersion: "limitless.omarchy-artifact-stage-input/0.1",
      handoffStatePath: serviceArtifactHandoffStatePath
    })
    runRuntime("service-artifact-stage", [], input)
  }

  function publishContribution() {
    if (!serviceReady) {
      errorText = "Enable the official service before publishing."
      return
    }
    if (!publicationDraftPath.trim().startsWith("/")) {
      errorText = "Choose an absolute path to one reviewed publication draft."
      return
    }
    if (!publicationPolicyAccepted) {
      errorText = "Review and accept the advertised public publication policy for this submission."
      return
    }
    if (!publicationPolicyReady || publicationPolicyDigest === "") {
      errorText = "Inspect the current public publication policy before publishing."
      return
    }
    runPublication("publish", publicationDraftPath.trim(), "", publicationPolicyDigest, null)
  }

  function inspectPublication() {
    if (!publicationStatePath.trim().startsWith("/")) {
      errorText = "Choose the absolute local state path for this publication."
      return
    }
    publicationWithdrawalArmed = false
    runPublication("status", "", publicationStatePath.trim(), null, null)
  }

  function withdrawPublication() {
    if (!publicationStatePath.trim().startsWith("/")) {
      errorText = "Choose the absolute local state path for this publication."
      return
    }
    if (!publicationWithdrawalArmed) {
      publicationWithdrawalArmed = true
      publicationSummary = "Withdrawal is durable. Select confirm only if this release should stop being eligible."
      return
    }
    publicationWithdrawalArmed = false
    runPublication("revoke", "", publicationStatePath.trim(), null, "publisher-withdrawal")
  }

  function openPublicationPolicy() {
    if (!publicationPolicyReady || !publicationPolicyUrl.startsWith("https://")) {
      errorText = "The verified publication policy URL is unavailable."
      return
    }
    Qt.openUrlExternally(publicationPolicyUrl)
  }

  function runPublication(nextOperation, draftPath, statePath, acceptedDigest, reasonCode) {
    publicationOperation = nextOperation
    var input = JSON.stringify({
      schemaVersion: "limitless.omarchy-publication-input/0.1",
      operation: nextOperation,
      draftPath: draftPath === "" ? null : draftPath,
      statePath: statePath === "" ? null : statePath,
      acceptedPublicationPolicyDigest: acceptedDigest,
      reasonCode: reasonCode
    })
    runRuntime("service-publication", [], input)
  }

  function runRuntime(nextOperation, arguments, stdinPayload) {
    if (command.running) return
    errorText = ""
    commandOutput = ""
    commandError = ""
    operation = nextOperation
    pendingInput = stdinPayload === undefined ? "" : String(stdinPayload)
    if (pluginRoot === "") {
      pendingInput = ""
      serviceObjective = ""
      errorText = "The Omarchy plugin root is unavailable. Reinstall this reviewed plugin before continuing."
      return
    }
    command.command = ["bash", pluginRoot + "/scripts/limitless-omarchy-runtime", nextOperation,
      "--plugin-root", pluginRoot].concat(arguments)
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
      runtimeReady = String(value.mode || "") === "local-only"
      headline = runtimeReady ? "Local Library ready" : "Set up Limitless Library"
      detail = runtimeReady
        ? "Choose a local catalog below, inspect the included example, or explicitly open the optional service section."
        : "Create an isolated local runtime to begin. Nothing will be shared."
      selectionReference = ""
      return
    }
    if (value.schemaVersion === "limitless.omarchy-service-status/0.1") {
      disposition = "status"
      serviceReady = String(value.mode || "") === "managed-service-ready"
      publicationPolicyAccepted = false
      if (serviceReady) {
        var service = value.service || {}
        var policy = value.policy || {}
        var publicationPolicy = value.publicationPolicy || null
        publicationPolicyReady = publicationPolicy
          && String(publicationPolicy.url || "").startsWith("https://")
          && String(publicationPolicy.digest || "").startsWith("sha256:")
        publicationPolicyUrl = publicationPolicyReady ? String(publicationPolicy.url) : ""
        publicationPolicyDigest = publicationPolicyReady ? String(publicationPolicy.digest) : ""
        publicationPolicySummary = publicationPolicyReady
          ? String(publicationPolicy.revision || "current") + " · " + publicationPolicyDigest
          : "Inspect the trust boundary to load the current public publication policy."
        headline = "Managed service verified"
        detail = "The release-pinned service authority and policy were verified. No task query was sent."
        serviceSummary = String(service.serviceId || "managed service") + " · "
          + String(service.defaultAudience || "private") + " · "
          + String(service.historyMode || "local-only") + " · "
          + String(policy.digest || "policy unavailable")
      } else {
        publicationPolicyReady = false
        publicationPolicyAccepted = false
        headline = "Managed service unavailable"
        detail = "Local Library use remains available. No remote selection was fabricated."
        serviceSummary = "Service unavailable; local reuse remains available."
      }
      selectionReference = ""
      return
    }
    if (value.schemaVersion === "limitless.omarchy-service-result/0.1") {
      runtimeReady = true
      disposition = String(value.disposition || "abstain")
      var serviceSelection = value.selection || null
      serviceArtifactHandoffStatePath = String(value.handoffStatePath || "")
      serviceArtifactStageAvailable = disposition === "exact-component"
        && serviceArtifactHandoffStatePath.startsWith("/")
      serviceArtifactStagedPath = ""
      selectionReference = serviceSelection && serviceSelection.title
        ? String(serviceSelection.title)
        : String(value.requestDigest || "")
      if (disposition === "exact-component") {
        var immutable = serviceSelection && serviceSelection.immutable ? serviceSelection.immutable : {}
        headline = "Verified component available"
        detail = String(serviceSelection.summary || "A compatible exact component was selected.")
          + " Stage its exact bytes for review before choosing a receiver-native installation."
      } else if (disposition === "source-free-method") {
        var serviceMethod = serviceSelection && serviceSelection.method ? serviceSelection.method : {}
        headline = "Verified method available"
        detail = String(serviceMethod.summary || serviceSelection.summary || "Apply the source-free method locally.")
      } else {
        headline = value.reason === "service-unavailable-local-still-available"
          ? "Managed service unavailable"
          : "Start fresh"
        detail = value.reason === "service-unavailable-local-still-available"
          ? "The managed query could not complete. Local Library use remains available."
          : "No eligible managed result was selected. No candidate details were disclosed."
      }
      serviceReady = value.reason !== "service-unavailable-local-still-available"
      publicationPolicyAccepted = false
      serviceSummary = serviceReady
        ? "Signed service result verified against the activated authority."
        : "Service unavailable; local reuse remains available."
      return
    }
    if (value.schemaVersion === "limitless.omarchy-artifact-stage-result/0.1") {
      runtimeReady = true
      disposition = "exact-component"
      serviceArtifactStageAvailable = false
      serviceArtifactStagedPath = String(value.path || "")
      selectionReference = String(value.digest || "")
      headline = "Verified component staged"
      detail = "Exact bytes were fetched with the locally bound continuation and verified before owner-only staging. No installation or enablement occurred."
      serviceSummary = "Receiver-native review and installation are still required."
      return
    }
    if (value.schemaVersion === "limitless.omarchy-publication-result/0.1") {
      runtimeReady = true
      var publicationAction = String(value.operation || "")
      var admission = String(value.admissionState || "unknown")
      publicationStatePath = String(value.statePath || publicationStatePath)
      selectionReference = String(value.submissionRef || "")
      if (publicationAction === "publish") {
        headline = "Contribution submitted"
        detail = "Only the files explicitly named by the reviewed draft were considered. Admission state: " + admission + "."
        publicationSummary = String(value.uploadedObjectCount || 0) + " missing object(s) uploaded · " + admission
      } else if (publicationAction === "revoke") {
        headline = "Contribution withdrawn"
        detail = "The active public release was withdrawn through the same anonymous installation authority."
        publicationSummary = "Withdrawn · " + admission
      } else {
        headline = "Contribution status verified"
        detail = "Current admission state: " + admission + ". No source bytes were resent."
        publicationSummary = "Status · " + admission
      }
      publicationPolicyAccepted = false
      publicationOperation = ""
      return
    }
    runtimeReady = true
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
    stdinEnabled: true
    onStarted: {
      if (root.pendingInput !== "") command.write(root.pendingInput + "\n")
      root.pendingInput = ""
      if (root.operation === "service-query") root.serviceObjective = ""
      if (root.operation === "service-publication" && root.publicationOperation === "publish")
        root.publicationPolicyAccepted = false
    }
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.commandOutput = String(text || "")
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.commandError = String(text || "").trim()
    }
    onExited: function(exitCode) {
      if (!root.opened) return
      if (exitCode === 0) root.applyResult(root.commandOutput)
      else root.errorText = root.commandError !== "" ? root.commandError : "The local runtime is unavailable."
      root.pendingInput = ""
      root.operation = ""
      root.publicationOperation = ""
    }
  }

  PanelWindow {
    visible: root.opened
    implicitWidth: content.implicitWidth
    implicitHeight: content.implicitHeight
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

      Local.PanelContents {
        id: content
        anchors.fill: parent
        panel: root
      }

      MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.RightButton
        onClicked: root.dismiss()
      }
    }
  }
}
