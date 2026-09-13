# Input Freeze for Omarchy

Input Freeze temporarily blocks keyboard and pointer input without locking your
Omarchy session. Media playback, downloads, renders, dashboards, and other
visible work continue normally while accidental input is ignored.

## Features

- Consumes all unmatched keyboard input through a dedicated Hyprland submap.
- Temporarily disconnects mice, touchpads, touchscreens, and tablet pointers.
- Keeps the toggle and a separate emergency recovery shortcut available while frozen.
- Watches for pointer devices connected after the freeze began.
- Restores only the devices recorded by the current freeze operation.
- Provides a themed Omarchy bar widget, status panel, CLI, and recovery action.
- Requires no root privileges and does not lock or suspend the session.

Input Freeze prevents accidental interaction. It is **not** an authentication or
security boundary; use the regular Omarchy lock screen when access control is
required.

## Requirements

- Omarchy with the Quattro shell plugin runtime
- Hyprland 0.55 or newer with Lua configuration
- `bash`, `python3` (standard library only), `jq`, `timeout` (coreutils), and `hyprctl`
- A private `XDG_RUNTIME_DIR` (normally provided by the login session)

## Install

Install and enable the widget:

```sh
omarchy plugin add https://github.com/pelukonline/omarchy-input-freeze.git --enable
```

Then add this safe include to `~/.config/hypr/bindings.lua`:

```lua
pcall(dofile, os.getenv("HOME") .. "/.config/omarchy/plugins/io.github.pelukonline.input-freeze/hyprland.lua")
```

Reload and verify Hyprland:

```sh
hyprctl reload
hyprctl configerrors
```

The `pcall` wrapper deliberately makes the include harmless after plugin
removal. It also avoids installer scripts modifying desktop configuration
without review.

## Usage

The default toggle is **Super + Ctrl + F12**. Press it once to freeze input and
again to restore it.

**Super + Ctrl + Shift + F12** runs emergency recovery independently of the
persistent state files. Both shortcuts are available in the frozen submap.

The bar icon opens a status panel when input is active. While frozen, the mouse
cannot operate the panel, so use the keyboard shortcut to restore input.
Right-clicking the icon while input is available runs the recovery action.

CLI commands:

```sh
~/.config/omarchy/plugins/io.github.pelukonline.input-freeze/input-freeze status
~/.config/omarchy/plugins/io.github.pelukonline.input-freeze/input-freeze enable
~/.config/omarchy/plugins/io.github.pelukonline.input-freeze/input-freeze disable
~/.config/omarchy/plugins/io.github.pelukonline.input-freeze/input-freeze toggle
~/.config/omarchy/plugins/io.github.pelukonline.input-freeze/input-freeze recover
```

### Change the shortcut

Edit `toggle_keys` near the top of `hyprland.lua`, then update the widget label:

```sh
omarchy bar set io.github.pelukonline.input-freeze shortcutLabel "Your shortcut"
hyprctl reload
```

Use a combination that does not overlap another shortcut. The same combination
must remain easy to reproduce while pointer input is unavailable.

To change emergency recovery, edit `recovery_keys` in `hyprland.lua`, update the
`recoveryShortcutLabel` widget setting, and reload Hyprland in the same way.

## Recovery

If the visible state and the devices ever disagree, run:

```sh
~/.config/omarchy/plugins/io.github.pelukonline.input-freeze/input-freeze recover
```

From another TTY, target the running Hyprland instance if required, then run the
same recovery command in the graphical user's environment. A Hyprland reload or
new login also clears transient per-device overrides.

Emergency `recover` bypasses state storage and re-enables currently connected
pointers even if state files are unsafe or unreadable. All actions share a
separate private runtime-directory lock, so recovery waits for an in-progress
freeze/ensure rather than racing it. If busy for five seconds it reports an error;
retry the shortcut. This does not prevent a later explicit freeze command.
Stale records are cleared by the next successful `ensure` or `disable` operation.

Freezing first validates the device list. Failed enumeration does not change
input. Normal restoration keeps the recorded devices until every restoration
and the keyboard reset succeeds, allowing retries after partial failures.
Emergency recovery attempts all currently listed pointers and reports failures;
it never reports success when an IPC operation fails. Panel action errors remain
visible across status refreshes until the next user action. IPC calls have a
three-second timeout (plus up to one second to force termination).

After updating to 0.1.2, run `hyprctl reload` and `hyprctl configerrors` to load
the new recovery binding. Restore input before updating from older versions,
which do not participate in the runtime coordination lock.

## Remove

Restore input before removal:

```sh
~/.config/omarchy/plugins/io.github.pelukonline.input-freeze/input-freeze disable
omarchy plugin remove io.github.pelukonline.input-freeze
hyprctl reload
```

The guarded `pcall(dofile, ...)` line may remain in `bindings.lua`, or you may
remove it. Runtime state is kept under
`~/.local/state/omarchy-input-freeze/` and contains device names only.

## Development

```sh
PLUGIN_DIR="$HOME/.config/omarchy/plugins/io.github.pelukonline.input-freeze"
omarchy plugin validate "$PLUGIN_DIR"
qmllint -I "$OMARCHY_PATH/shell" \
  "$PLUGIN_DIR/BarWidget.qml" \
  "$PLUGIN_DIR/Panel.qml" \
  "$PLUGIN_DIR/StateService.qml"
bash -n "$PLUGIN_DIR/input-freeze"
```

## Privacy and privileges

The plugin runs with the current user's permissions. It never requests root,
reads key contents, sends telemetry, or uses the network. Its state file stores
only the Hyprland names of pointer devices temporarily disabled by the plugin.

State storage is handled by `state.py`, while desktop operations remain in Bash.
The Python parent holds a non-truncating file lock for the complete Bash action.
State files are accessed relative to a validated directory descriptor using
`O_NOFOLLOW`; non-regular files and multiple hard links are rejected. Owned legacy
directories/files are tightened to 0700/0600 after descriptor validation. Device
records use exclusive temporary files and atomic replacement. This prevents the
reported symlink overwrite; it is not isolation from arbitrary code running as
the same user.

Coordination with emergency recovery uses an exclusively locked, validated 0700
directory at `$XDG_RUNTIME_DIR/omarchy-input-freeze`, falling back to the login
runtime path `/run/user/<uid>` when the variable is absent. It stores no device
data and is never replaced or removed by the helper. Unsafe runtime paths are
rejected, including for emergency recovery; in that case use the documented
Hyprland reload/new-login fallback.

## License

MIT
