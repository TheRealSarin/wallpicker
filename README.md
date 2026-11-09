# wallpicker

A small wallpaper picker for Wayland compositors with layer-shell support
(Hyprland, Sway, river, niri and other wlroots-style compositors). It opens a
strip of thumbnails at the bottom of the screen; scroll through it and each
wallpaper is previewed live on your desktop. Press Enter to keep it or Escape to
go back to the one you had.

No text, no buttons: just the thumbnails.

## Features

- Live preview on the real desktop while you scroll, debounced so fast
  scrolling does not queue up transitions.
- Escape restores the wallpaper you started with.
- Works with any wallpaper setter. [awww](https://codeberg.org/LGFae/awww) /
  [swww](https://github.com/LGFae/swww) are the defaults, but `swaybg` or
  your own script work too.
- One TOML file controls the folder, commands, size, position, colours,
  radii, opacity and key bindings. An optional CSS file is layered on top.
- Thumbnails are cached in `~/.cache/wallpicker`, so it opens instantly after
  the first run.
- Single instance: launching it again while it is open closes it, so one key
  binding toggles it.
- Opens on the focused monitor under Hyprland, or a monitor you name.

## Requirements

- Python 3.11 or newer
- GTK 3, [gtk-layer-shell](https://github.com/wmww/gtk-layer-shell) and
  PyGObject
- A wallpaper setter, `awww` by default

On Arch Linux:

```sh
sudo pacman -S python-gobject gtk3 gtk-layer-shell awww
```

WebP and AVIF thumbnails need `webp-pixbuf-loader` and `libavif` respectively.

## Install

```sh
git clone https://github.com/TheRealSarin/wallpicker.git
cd wallpicker
./install.sh --desktop
```

This links `wallpicker` into `~/.local/bin` and, with `--desktop`, adds a
launcher entry so it shows up in rofi, wofi, fuzzel and similar launchers. Pass
a different directory to link somewhere else: `./install.sh ~/bin`.

It can also be run straight from the checkout with `bin/wallpicker`.

## Usage

```
wallpicker [DIRECTORY] [-c CONFIG] [--list] [--check-config] [-v] [--version]
```

| Input | Action |
| --- | --- |
| Mouse wheel, arrow keys, `h` `j` `k` `l`, Tab | Move through the wallpapers |
| Enter, Space, clicking the highlighted thumbnail | Apply and close |
| Escape, `q`, right click | Restore the previous wallpaper and close |
| Home / End | Jump to the first / last wallpaper |

`DIRECTORY` overrides the folder from the config for one run. `--list` prints
the files that would be shown, and `--check-config` validates the config file.

### Hyprland

Bind a key and give the window blur and an animation with a layer rule
matching the `wallpicker` namespace. With the Lua config:

```lua
hl.bind("SUPER + SHIFT + W", hl.dsp.exec_cmd("wallpicker"))
hl.layer_rule({ match = { namespace = "wallpicker" }, animation = "slide bottom", blur = true, ignore_alpha = 0.5 })
```

With `hyprland.conf`, use the equivalent `bind` and `layerrule` lines for your
Hyprland version. Make sure your wallpaper daemon (`awww-daemon`) is started
at login.

## Configuration

The config file lives at `~/.config/wallpicker/config.toml` (or
`$XDG_CONFIG_HOME/wallpicker/config.toml`). Every option is optional; copy
[`examples/config.toml`](examples/config.toml) for a file with all the
defaults filled in and change what you like. Unknown options and invalid
values are reported instead of silently ignored.

### `[general]`

| Option | Default | Description |
| --- | --- | --- |
| `directory` | `"~/Pictures/Wallpapers"` | Folder to read wallpapers from |
| `recursive` | `true` | Include subfolders (hidden folders are skipped) |
| `state_file` | `"~/.cache/wallpicker/current"` | File holding the current wallpaper path, used to start on it and to restore it on cancel |
| `live_preview` | `true` | Preview on the desktop while scrolling |
| `preview_delay_ms` | `220` | How long the selection has to settle before previewing |
| `monitor` | `"focused"` | `"focused"` (Hyprland), a connector name such as `"DP-1"` (Hyprland), or a GDK monitor index such as `"0"` |

### `[commands]`

Each command is either a list of arguments, run directly, or a string, run by
`sh -c`. `{path}` is replaced with the wallpaper path (shell-quoted in the
string form). A leading `~` in the program is expanded.

| Option | Default | Description |
| --- | --- | --- |
| `preview` | `awww img {path}` with a quick fade | Run while scrolling and to restore on cancel |
| `apply` | `awww img {path}` with a grow transition | Run when a wallpaper is chosen |

Examples for other setters:

```toml
[commands]
preview = "swww img {path} --transition-type fade --transition-duration 0.3"
apply = "swww img {path} --transition-type grow"
```

```toml
[commands]
preview = "pkill -x swaybg; swaybg -m fill -i {path} &"
apply = "pkill -x swaybg; swaybg -m fill -i {path} &"
```

Pointing `apply` at your own script is a good way to also regenerate a colour
scheme, update a lock screen image, and so on:

```toml
[commands]
apply = ["~/.config/hypr/wallpaper.sh", "{path}"]
```

### `[layout]`

| Option | Default | Description |
| --- | --- | --- |
| `position` | `"bottom"` | `"bottom"`, `"top"` or `"center"` |
| `margin` | `120` | Gap between the panel and the screen edge, in pixels |
| `visible` | `5` | Thumbnails visible at once (capped by the screen width) |
| `thumb_width` | `288` | Thumbnail width |
| `thumb_height` | `162` | Thumbnail height |
| `spacing` | `8` | Gap between thumbnails |
| `item_padding` | `6` | Padding between a thumbnail and its selection highlight |

### `[appearance]`

Colours are `#rrggbb` or `#rrggbbaa`.

| Option | Default | Description |
| --- | --- | --- |
| `background` | `"#0d1117b3"` | Panel background |
| `border` | `"#30363d"` | Panel border colour |
| `border_width` | `2` | Panel border width |
| `radius` | `16` | Panel corner radius |
| `padding` | `16` | Space inside the panel |
| `selection` | `"#1f6feb73"` | Highlight behind the selected thumbnail |
| `item_radius` | `10` | Corner radius of the highlight |
| `thumb_radius` | `8` | Corner radius of the thumbnails |
| `dim` | `0.55` | Opacity of thumbnails that are not selected, `0` to `1` |
| `placeholder` | `"#161b22"` | Fill shown while a thumbnail is loading |

### `[keys]`

Each action takes a list of GDK key names (as printed by `wev` or listed in
`gdk/gdkkeysyms.h` without the `GDK_KEY_` prefix).

| Option | Default |
| --- | --- |
| `next` | `["Right", "Down", "l", "j", "Tab"]` |
| `previous` | `["Left", "Up", "h", "k", "ISO_Left_Tab"]` |
| `first` | `["Home"]` |
| `last` | `["End"]` |
| `apply` | `["Return", "KP_Enter", "space"]` |
| `cancel` | `["Escape", "q"]` |

### Custom CSS

For anything the options do not cover, `~/.config/wallpicker/style.css` is
loaded after the built-in style. The panel has the class `wallpicker-panel`:

```css
.wallpicker-panel {
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
}
```

A different path can be set with a top-level `stylesheet = "..."` in the
config file.

## Development

```sh
python3 -m unittest discover -s tests -t .
```

## License

[MIT](LICENSE)
