import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "io.github.pelukonline.input-freeze"

  readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false
  readonly property bool popoutSwitchClosing: panelLoader.item
    ? panelLoader.item.popoutSwitchClosing === true
    : false
  readonly property bool frozen: freezeState.active
  readonly property string shortcutLabel: String(setting("shortcutLabel", "Super + Ctrl + F12"))

  function injectPanel() {
    var target = panelLoader.item
    if (!target) return
    target.bar = root.bar
    target.settings = root.settings
    target.anchorItem = button
    target.hostWidget = root
    target.freezeState = freezeState
  }

  function open() { if (panelLoader.item) panelLoader.item.open() }
  function close() { if (panelLoader.item) panelLoader.item.close() }
  function toggle() { if (panelLoader.item) panelLoader.item.toggle() }
  function closeForPopoutSwitch() {
    if (panelLoader.item && panelLoader.item.closeForPopoutSwitch)
      panelLoader.item.closeForPopoutSwitch()
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  onBarChanged: injectPanel()
  onSettingsChanged: injectPanel()

  StateService {
    id: freezeState
    refreshIntervalMs: Number(root.setting("refreshIntervalMs", 1000))
  }

  Loader {
    id: panelLoader
    active: true
    source: Qt.resolvedUrl("Panel.qml")
    visible: false
    onLoaded: {
      root.injectPanel()
      Qt.callLater(root.injectPanel)
    }
  }

  IpcHandler {
    target: root.moduleName
    function open(): void { root.open() }
    function close(): void { root.close() }
    function show(): void { root.open() }
    function hide(): void { root.close() }
    function toggle(): void { root.toggle() }
    function freeze(): string { freezeState.enable(); return "ok" }
    function unfreeze(): string { freezeState.disable(); return "ok" }
    function recover(): string { freezeState.recover(); return "ok" }
    function status(): string { return freezeState.statusText }
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    tooltipText: "Input Freeze · " + freezeState.statusText
    iconComponent: Component {
      Item {
        Text {
          anchors.centerIn: parent
          text: root.frozen ? "󰌾" : "󰌿"
          color: root.frozen ? Color.accent : (root.bar ? root.bar.barForeground : Color.foreground)
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.title
        }
      }
    }
    onPressed: function(buttonCode) {
      if (buttonCode === Qt.RightButton) freezeState.recover()
      else root.toggle()
    }
  }
}
