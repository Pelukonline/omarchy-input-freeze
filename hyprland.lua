-- Input Freeze keymap integration for Omarchy / Hyprland.
-- Change this one value if the default shortcut conflicts with your setup.
local toggle_keys = "SUPER + CTRL + F12"
local plugin_dir = os.getenv("HOME") .. "/.config/omarchy/plugins/io.github.pelukonline.input-freeze"
local command = plugin_dir .. "/input-freeze"

-- Universal keeps the recovery shortcut available inside the restricted submap.
hl.bind(toggle_keys, hl.dsp.exec_cmd(command .. " toggle"), {
  description = "Toggle Input Freeze",
  submap_universal = true,
})

hl.define_submap("input-freeze", function()
  -- Consume every otherwise-unmatched key instead of forwarding it to the app.
  hl.bind("catchall", hl.dsp.exec_cmd("true"))
end)
