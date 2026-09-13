import QtQuick
import Quickshell
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "io.github.pelukonline.input-freeze"
  manageIpc: false

  property var anchorItem: null
  property var hostWidget: null
  property var freezeState: null
  readonly property var barIdentity: hostWidget || root
  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color dim: Qt.darker(foreground, 1.55)
  readonly property color urgent: bar ? bar.urgent : Color.accent
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family
  readonly property string shortcutLabel: String(setting("shortcutLabel", "Super + Ctrl + F12"))
  readonly property string recoveryShortcutLabel: String(setting("recoveryShortcutLabel", "Super + Ctrl + Shift + F12"))

  function open() {
    if (freezeState) freezeState.refresh()
    root.controller.show()
  }

  function close() { root.controller.hide() }
  function toggle() { if (root.opened) close(); else open() }
  function closeForPopoutSwitch() { close() }
  function switchPanel(direction) {
    if (bar && typeof bar.switchPanelFrom === "function")
      return bar.switchPanelFrom(barIdentity, direction)
    return false
  }

  function toggleFreeze() {
    close()
    Qt.callLater(function() { if (freezeState) freezeState.toggle() })
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(380))
    contentHeight: panel.fittedContentHeight(content.implicitHeight)

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onActivateRequested: root.toggleFreeze()

      Column {
        id: content
        width: parent.width
        spacing: Style.space(12)

        Text {
          width: parent.width
          text: "INPUT FREEZE"
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          font.bold: true
        }

        Text {
          width: parent.width
          text: !root.freezeState || !root.freezeState.available ? "Status unavailable"
            : root.freezeState.active ? "󰌾  Input frozen" : "󰌿  Input active"
          color: root.freezeState && root.freezeState.active ? Color.accent : root.foreground
          font.family: root.fontFamily
          font.pixelSize: Style.font.title
          font.bold: true
        }

        Text {
          width: parent.width
          text: root.freezeState && root.freezeState.active
            ? "Keyboard events are being consumed and pointer devices are disconnected from the cursor."
            : "Keep media, downloads, renders, and visible apps running while accidental input is blocked."
          color: root.foreground
          font.family: root.fontFamily
          font.pixelSize: Style.font.body
          wrapMode: Text.WordWrap
        }

        Text {
          width: parent.width
          text: "Toggle shortcut  ·  " + root.shortcutLabel
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.bodySmall
          wrapMode: Text.WordWrap
        }

        Text {
          width: parent.width
          text: "Emergency recovery  ·  " + root.recoveryShortcutLabel
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.bodySmall
          wrapMode: Text.WordWrap
        }

        Button {
          width: parent.width
          text: root.freezeState && root.freezeState.active ? "Restore input" : "Freeze input"
          iconText: root.freezeState && root.freezeState.active ? "󰌿" : "󰌾"
          foreground: root.foreground
          fontFamily: root.fontFamily
          bordered: true
          enabled: root.freezeState && !root.freezeState.busy
          onClicked: root.toggleFreeze()
        }

        Text {
          visible: root.freezeState && root.freezeState.lastError !== ""
          width: parent.width
          text: root.freezeState ? root.freezeState.lastError : ""
          color: root.urgent
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          wrapMode: Text.WordWrap
        }

        Text {
          width: parent.width
          text: "This prevents accidents; it is not a security lock. Right-click the bar icon to recover input if state becomes inconsistent."
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          wrapMode: Text.WordWrap
        }
      }
    }
  }
}
