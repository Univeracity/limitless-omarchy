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
  property string serviceProfilePath: ""
  property string serviceObjective: ""
  property string serviceAccessToken: ""
  property string omarchyRelease: ""
  property bool serviceExpanded: false
  property bool serviceReady: false
  property string serviceSummary: "No managed-service request has been made."
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
    if (payload.serviceProfilePath !== undefined) {
      serviceProfilePath = String(payload.serviceProfilePath)
      serviceExpanded = serviceProfilePath !== ""
    }
    if (payload.omarchyRelease !== undefined) omarchyRelease = String(payload.omarchyRelease)
    serviceReady = false
    serviceSummary = "No managed-service request has been made."
    opened = true
    refresh()
    Qt.callLater(function() { if (opened) keyCatcher.forceActiveFocus() })
  }

  function close() {
    opened = false
    serviceAccessToken = ""
    serviceObjective = ""
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

  function inspectService() {
    if (serviceProfilePath.trim() === "") {
      errorText = "Choose an absolute managed-service profile before inspecting it."
      return
    }
    runRuntime("service-inspect", ["--profile", serviceProfilePath.trim()])
  }

  function queryService() {
    if (serviceProfilePath.trim() === "") {
      errorText = "Choose an absolute managed-service profile before querying it."
      return
    }
    if (serviceObjective.trim() === "") {
      errorText = "Describe the customization to search for before sending a managed query."
      return
    }
    var arguments = ["--profile", serviceProfilePath.trim()]
    if (omarchyRelease.trim() !== "") arguments = arguments.concat(["--omarchy-release", omarchyRelease.trim()])
    var input = JSON.stringify({
      schemaVersion: "limitless.omarchy-service-query-input/0.1",
      objective: serviceObjective.trim(),
      accessToken: serviceAccessToken === "" ? null : serviceAccessToken
    })
    runRuntime("service-query", arguments, input)
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
      serviceAccessToken = ""
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
        ? "Choose a local catalog below, inspect the included example, or explicitly open the managed-service section."
        : "Create an isolated local runtime to begin. Nothing will be shared."
      selectionReference = ""
      return
    }
    if (value.schemaVersion === "limitless.omarchy-service-status/0.1") {
      disposition = "status"
      serviceReady = String(value.mode || "") === "managed-service-ready"
      if (serviceReady) {
        var service = value.service || {}
        var policy = value.policy || {}
        headline = "Managed service verified"
        detail = "The pinned service authority and policy match this profile. No task query was sent."
        serviceSummary = String(service.serviceId || "managed service") + " · "
          + String(service.dataUseMode || "unknown mode") + " · "
          + String(policy.digest || "policy unavailable")
      } else {
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
      var serviceDecision = value.decision || null
      var serviceSelection = serviceDecision && serviceDecision.selection ? serviceDecision.selection : null
      selectionReference = serviceSelection && serviceSelection.title
        ? String(serviceSelection.title)
        : String(value.requestDigest || "")
      if (disposition === "exact-component") {
        var immutable = serviceSelection && serviceSelection.immutable ? serviceSelection.immutable : {}
        headline = "Verified component available"
        detail = String(serviceSelection.summary || "A compatible exact component was selected.")
          + " Review " + String(immutable.uri || "the pinned source")
          + " and continue through Omarchy's native add flow."
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
      serviceSummary = serviceReady
        ? "Signed managed result verified against the selected profile."
        : "Service unavailable; local reuse remains available."
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
      root.serviceAccessToken = ""
      if (root.operation === "service-query") root.serviceObjective = ""
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
      root.serviceAccessToken = ""
      root.operation = ""
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
