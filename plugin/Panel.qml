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
  property string serviceArtifactReviewPath: ""
  property bool serviceArtifactReviewAvailable: false
  property bool serviceArtifactInstallAvailable: false
  property string serviceArtifactInstallationStatePath: ""
  property bool serviceArtifactEnableAvailable: false
  property string serviceArtifactAdoptionReceiptPath: ""
  property bool publicationExpanded: false
  property string publicationDraftPath: ""
  property string publicationStatePath: ""
  property bool publicationPolicyAccepted: false
  property bool publicationPolicyReady: false
  property string publicationPolicyUrl: ""
  property string publicationPolicyDigest: ""
  property string publicationPolicySummary: "Inspect the trust boundary to load the current public publication policy."
  property bool publicationWithdrawalArmed: false
  property string defaultAgent: ""
  property var additionalAgentIds: []
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
  property string agentSummary: "The current Omarchy default will be connected after local setup."
  property string agentReportPath: ""
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
    serviceArtifactReviewPath = ""
    serviceArtifactReviewAvailable = false
    serviceArtifactInstallAvailable = false
    serviceArtifactInstallationStatePath = ""
    serviceArtifactEnableAvailable = false
    serviceArtifactAdoptionReceiptPath = ""
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

  function agentLabel(agentId) {
    for (var index = 0; index < agentOptions.length; index += 1) {
      if (String(agentOptions[index].id) === String(agentId)) return String(agentOptions[index].label)
    }
    return String(agentId)
  }

  function hasAdditionalAgent(agentId) {
    return additionalAgentIds.indexOf(String(agentId)) >= 0
  }

  function toggleAdditionalAgent(agentId) {
    var target = String(agentId)
    if (target === defaultAgent) return
    var next = additionalAgentIds.slice(0)
    var position = next.indexOf(target)
    if (position >= 0) next.splice(position, 1)
    else next.push(target)
    additionalAgentIds = next
  }

  function refreshAgentStatus() {
    if (runtimeReady) runRuntime("agent-status", [])
  }

  function reconcileAgents() {
    var arguments = []
    for (var index = 0; index < additionalAgentIds.length; index += 1)
      arguments = arguments.concat(["--additional-agent", String(additionalAgentIds[index])])
    runRuntime("agent-reconcile", arguments)
  }

  function disconnectAgents() {
    runRuntime("agent-disconnect", [])
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

  function prepareServiceArtifactReview() {
    if (!serviceArtifactReviewAvailable || !serviceArtifactHandoffStatePath.startsWith("/")) {
      errorText = "No locally bound exact Omarchy bundle is available."
      return
    }
    var input = JSON.stringify({
      schemaVersion: "limitless.omarchy-artifact-review-input/0.1",
      handoffStatePath: serviceArtifactHandoffStatePath
    })
    runRuntime("service-artifact-review", [], input)
  }

  function installServiceArtifactDisabled() {
    if (!serviceArtifactInstallAvailable || !serviceArtifactHandoffStatePath.startsWith("/")) {
      errorText = "Review and validate one exact Omarchy bundle before installing it."
      return
    }
    var input = JSON.stringify({
      schemaVersion: "limitless.omarchy-artifact-install-input/0.1",
      handoffStatePath: serviceArtifactHandoffStatePath
    })
    runRuntime("service-artifact-install", [], input)
  }

  function enableServiceArtifact() {
    if (!serviceArtifactEnableAvailable || !serviceArtifactInstallationStatePath.startsWith("/")) {
      errorText = "No signed disabled installation is awaiting explicit enablement."
      return
    }
    var input = JSON.stringify({
      schemaVersion: "limitless.omarchy-artifact-enable-input/0.1",
      installationStatePath: serviceArtifactInstallationStatePath
    })
    runRuntime("service-artifact-enable", [], input)
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
    if (value.schemaVersion === "limitless.omarchy-agent-connection-status/0.1") {
      runtimeReady = true
      defaultAgent = value.defaultAgent === null || value.defaultAgent === undefined ? "" : String(value.defaultAgent)
      additionalAgentIds = Array.isArray(value.additionalAgents) ? value.additionalAgents.map(String) : []
      agentReportPath = String(value.reportPath || "")
      var connections = Array.isArray(value.connections) ? value.connections : []
      var defaultStatus = ""
      for (var connectionIndex = 0; connectionIndex < connections.length; connectionIndex += 1) {
        var connection = connections[connectionIndex] || {}
        if (String(connection.agent || "") === defaultAgent) {
          defaultStatus = String(connection.status || "")
          break
        }
      }
      if (defaultAgent === "") {
        agentSummary = "Choose a default agent in Omarchy Setup › Defaults › Agent, then return here to connect it."
      } else if (defaultStatus === "connected") {
        agentSummary = "Default: " + agentLabel(defaultAgent) + " · local MCP connected."
      } else if (defaultStatus === "available") {
        agentSummary = "Default: " + agentLabel(defaultAgent) + " · MCP setup is not yet supported by its current client."
      } else {
        agentSummary = "Default: " + agentLabel(defaultAgent) + " · local MCP is not connected. Select Connect to retry."
      }
      return
    }
    if (value.schemaVersion === "limitless.omarchy-agent-connection-report/0.1") {
      runtimeReady = true
      defaultAgent = value.defaultAgent === null || value.defaultAgent === undefined ? "" : String(value.defaultAgent)
      additionalAgentIds = Array.isArray(value.additionalAgents) ? value.additionalAgents.map(String) : []
      agentReportPath = String(value.reportPath || "")
      var results = Array.isArray(value.results) ? value.results : []
      var connectedCount = 0
      var attentionCount = 0
      for (var resultIndex = 0; resultIndex < results.length; resultIndex += 1) {
        var result = results[resultIndex] || {}
        if (String(result.status || "") === "connected") connectedCount += 1
        else if (String(result.status || "") !== "disconnected") attentionCount += 1
      }
      headline = value.action === "disconnect" ? "Agent connections updated" : "Limitless ready for agents"
      detail = connectedCount > 0
        ? String(connectedCount) + " selected agent connection(s) are ready."
        : "Local Library setup completed. Review the agent connection result below."
      agentSummary = attentionCount > 0
        ? "Some agent targets need attention. Details are saved locally."
        : "Selected agent connections are ready."
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
      serviceArtifactReviewAvailable = serviceArtifactStageAvailable
      serviceArtifactStagedPath = ""
      serviceArtifactReviewPath = ""
      serviceArtifactInstallAvailable = false
      serviceArtifactInstallationStatePath = ""
      serviceArtifactEnableAvailable = false
      serviceArtifactAdoptionReceiptPath = ""
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
    if (value.schemaVersion === "limitless.omarchy-artifact-review-result/0.1") {
      runtimeReady = true
      disposition = "exact-component"
      serviceArtifactStageAvailable = false
      serviceArtifactReviewAvailable = false
      serviceArtifactStagedPath = String(value.bundlePath || "")
      serviceArtifactReviewPath = String(value.reviewPath || "")
      selectionReference = String(value.digest || "")
      var validation = value.nativeValidation || {}
      if (String(validation.status || "invalid") === "valid") {
        serviceArtifactInstallAvailable = true
        headline = "Verified plugin ready for review"
        detail = "Exact bundle files were materialized without overwrite and passed Omarchy's native validator. Review them before choosing install disabled."
        serviceSummary = "Installation and enablement remain separate explicit actions."
      } else {
        serviceArtifactInstallAvailable = false
        headline = "Plugin requires review"
        detail = "Exact bundle files were materialized without overwrite, but Omarchy's native validator did not accept the tree. Nothing was installed or enabled."
        serviceSummary = String(validation.stderr || validation.stdout || "Native validation failed closed.")
      }
      return
    }
    if (value.schemaVersion === "limitless.omarchy-artifact-install-result/0.1") {
      runtimeReady = true
      disposition = "exact-component"
      serviceArtifactInstallAvailable = false
      serviceArtifactEnableAvailable = true
      serviceArtifactInstallationStatePath = String(value.installationStatePath || "")
      serviceArtifactReviewPath = String(value.installPath || serviceArtifactReviewPath)
      selectionReference = String(value.pluginId || value.digest || "")
      headline = "Verified plugin installed disabled"
      detail = "Exact reviewed bytes are installed, but Omarchy confirms they are disabled. Enablement still requires a separate explicit action."
      serviceSummary = "No plugin entry point has been invoked."
      return
    }
    if (value.schemaVersion === "limitless.omarchy-artifact-adoption-result/0.1") {
      runtimeReady = true
      disposition = "exact-component"
      serviceArtifactInstallAvailable = false
      serviceArtifactEnableAvailable = false
      serviceArtifactAdoptionReceiptPath = String(value.adoptionReceiptPath || "")
      selectionReference = String(value.pluginId || value.digest || "")
      var invocation = value.observedInvocation || {}
      headline = invocation.observed === true ? "Verified adoption observed" : "Enablement requires review"
      detail = invocation.observed === true
        ? "Omarchy enabled and invoked the reviewed exact plugin. Signed local evidence now binds selection, installation, enablement, and observed use."
        : "Omarchy did not provide sufficient observed-use evidence."
      serviceSummary = serviceArtifactAdoptionReceiptPath === ""
        ? "No adoption evidence was retained."
        : "Local adoption evidence: " + serviceArtifactAdoptionReceiptPath
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
      var completedOperation = root.operation
      if (exitCode === 0) root.applyResult(root.commandOutput)
      else root.errorText = root.commandError !== "" ? root.commandError : "The local runtime is unavailable."
      root.pendingInput = ""
      root.operation = ""
      root.publicationOperation = ""
      if (completedOperation === "status" && root.runtimeReady)
        Qt.callLater(function() { if (root.opened) root.refreshAgentStatus() })
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
