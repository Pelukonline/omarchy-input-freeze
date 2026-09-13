import QtQuick
import Quickshell.Io

Item {
  id: root

  property int refreshIntervalMs: 1000
  property bool active: false
  property bool available: false
  property bool busy: actionProcess.running
  property int pointerCount: 0
  property string statusText: available ? (active ? "Input frozen" : "Input active") : "Unavailable"
  property string lastError: ""

  readonly property string helperPath: {
    var value = String(Qt.resolvedUrl("input-freeze"))
    if (value.indexOf("file://") === 0) value = value.substring(7)
    return decodeURIComponent(value)
  }

  function refresh() {
    if (statusProcess.running || helperPath === "") return
    statusProcess.command = [helperPath, "status"]
    statusProcess.running = true
  }

  function run(action) {
    if (busy || helperPath === "") return
    root.lastError = ""
    actionProcess.command = [helperPath, action]
    actionProcess.running = true
  }

  function enable() { run("enable") }
  function disable() { run("disable") }
  function toggle() { run("toggle") }
  function recover() { run("recover") }

  Timer {
    interval: Math.max(500, root.refreshIntervalMs)
    repeat: true
    running: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  Timer {
    interval: 1000
    repeat: true
    running: root.active
    onTriggered: {
      if (!ensureProcess.running && root.helperPath !== "") {
        ensureProcess.command = [root.helperPath, "ensure"]
        ensureProcess.running = true
      }
    }
  }

  Process {
    id: statusProcess
    running: false
    command: []
    stdout: StdioCollector {
      id: statusStdout
      waitForEnd: true
    }
    stderr: StdioCollector {
      id: statusStderr
      waitForEnd: true
    }
    onExited: function(exitCode) {
      if (exitCode !== 0) {
        root.available = false
        root.lastError = String(statusStderr.text || "Could not read Input Freeze status").trim()
        return
      }
      try {
        var result = JSON.parse(String(statusStdout.text || "{}"))
        root.available = result.ok === true
        root.active = result.active === true
        root.pointerCount = Number(result.pointerCount || 0)
        root.lastError = ""
      } catch (error) {
        root.available = false
        root.lastError = "Input Freeze returned invalid status"
      }
    }
  }

  Process {
    id: actionProcess
    running: false
    command: []
    stderr: StdioCollector {
      id: actionStderr
      waitForEnd: true
    }
    onExited: function(exitCode) {
      if (exitCode !== 0)
        root.lastError = String(actionStderr.text || "Input Freeze action failed").trim()
      root.refresh()
    }
  }

  Process {
    id: ensureProcess
    running: false
    command: []
    onExited: function(exitCode) {
      if (exitCode !== 0) root.lastError = "Input Freeze could not secure a newly connected pointer"
    }
  }
}
