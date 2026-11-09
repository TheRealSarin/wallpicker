import json
import logging
import math
import os
import subprocess

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
import cairo
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, GtkLayerShell

from . import commands
from .config import cache_home, parse_color
from .library import cover_crop, list_wallpapers, read_state, thumbnail_key, write_state

LOG = logging.getLogger("wallpicker")
APP_ID = "io.github.therealsarin.wallpicker"
SCROLL_ANIMATION_US = 180000


def css_rgba(value):
    r, g, b, a = parse_color(value)
    return f"rgba({round(r * 255)}, {round(g * 255)}, {round(b * 255)}, {a:.3f})"


def build_css(appearance):
    return f"""
window {{ background: transparent; }}
.wallpicker-panel {{
    background: {css_rgba(appearance.background)};
    border: {appearance.border_width}px solid {css_rgba(appearance.border)};
    border-radius: {appearance.radius}px;
    padding: {appearance.padding}px;
}}
.wallpicker-empty {{ color: #e6edf3; padding: 24px; }}
scrollbar {{ opacity: 0; min-height: 0; min-width: 0; }}
""".encode()


def round_rect(cr, x, y, w, h, r):
    r = max(0, min(r, w / 2, h / 2))
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


class Thumbnailer:
    def __init__(self, width, height, radius):
        self.width = width
        self.height = height
        self.radius = radius
        self.directory = os.path.join(cache_home(), "wallpicker", "thumbs")

    def pixbuf(self, path):
        os.makedirs(self.directory, exist_ok=True)
        key = thumbnail_key(path, os.stat(path).st_mtime_ns, self.width, self.height)
        cached = os.path.join(self.directory, key + ".png")
        if os.path.exists(cached):
            return GdkPixbuf.Pixbuf.new_from_file(cached)
        source = GdkPixbuf.Pixbuf.new_from_file(path)
        w, h, x, y = cover_crop(source.get_width(), source.get_height(), self.width, self.height)
        scaled = source.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR)
        thumb = scaled.new_subpixbuf(x, y, self.width, self.height).copy()
        thumb.savev(cached, "png", [], [])
        return thumb

    def surface(self, path):
        pixbuf = self.pixbuf(path)
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.width, self.height)
        cr = cairo.Context(surface)
        round_rect(cr, 0, 0, self.width, self.height, self.radius)
        cr.clip()
        Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
        cr.paint()
        return surface


def hyprland_monitors():
    try:
        output = subprocess.check_output(["hyprctl", "monitors", "-j"], timeout=1, stderr=subprocess.DEVNULL)
        return json.loads(output)
    except (OSError, subprocess.SubprocessError, ValueError):
        return []


def pick_monitor(display, setting):
    if setting.isdigit():
        index = int(setting)
        if index < display.get_n_monitors():
            return display.get_monitor(index)
        LOG.warning("monitor %s does not exist, using the default", setting)
        return None
    monitors = hyprland_monitors()
    if setting == "focused":
        target = next((m for m in monitors if m.get("focused")), None)
    else:
        target = next((m for m in monitors if m.get("name") == setting), None)
        if target is None:
            LOG.warning("monitor %r not found, using the default", setting)
    if target is None:
        return None
    return display.get_monitor_at_point(target["x"] + target["width"] // 2, target["y"] + target["height"] // 2)


class Picker(Gtk.Window):
    def __init__(self, app, config, directory):
        super().__init__(application=app, title="wallpicker")
        self.config = config
        self.layout = config.layout
        self.appearance = config.appearance
        self.files = list_wallpapers(directory, config.general.recursive)
        self.original = read_state(config.general.state_file)
        self.index = self.files.index(self.original) if self.original in self.files else 0
        self.previewed = self.original
        self.preview_source = 0
        self.scroll_source = 0
        self.finished = False
        self.items = []
        self.item_w = self.layout.thumb_width + self.layout.item_padding * 2
        self.item_h = self.layout.thumb_height + self.layout.item_padding * 2
        self.selection = parse_color(self.appearance.selection)
        self.placeholder = parse_color(self.appearance.placeholder)
        self.thumbnailer = Thumbnailer(self.layout.thumb_width, self.layout.thumb_height, self.appearance.thumb_radius)
        self.keymap = self._build_keymap(config.keys)

        self._setup_layer_shell()
        self._setup_style()
        self._build()

        self.connect("key-press-event", self.on_key)
        self.connect("scroll-event", self.on_scroll)
        self.add_events(Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.SMOOTH_SCROLL_MASK)
        self.show_all()

        if self.files:
            self.select(self.index, preview=False, animate=False)
            GLib.idle_add(self._load_next, iter(self._load_order()))

    def _build_keymap(self, keys):
        keymap = {}
        for action in ("next", "previous", "first", "last", "apply", "cancel"):
            for name in getattr(keys, action):
                value = Gdk.keyval_from_name(name)
                if value in (0, Gdk.KEY_VoidSymbol):
                    LOG.warning("unknown key name %r in [keys] %s", name, action)
                    continue
                keymap[value] = action
        return keymap

    def _setup_layer_shell(self):
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_namespace(self, "wallpicker")
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
        edge = {"bottom": GtkLayerShell.Edge.BOTTOM, "top": GtkLayerShell.Edge.TOP}.get(self.layout.position)
        if edge is not None:
            GtkLayerShell.set_anchor(self, edge, True)
            GtkLayerShell.set_margin(self, edge, self.layout.margin)
        monitor = pick_monitor(Gdk.Display.get_default(), self.config.general.monitor)
        if monitor is not None:
            GtkLayerShell.set_monitor(self, monitor)
        self.monitor_width = (monitor or Gdk.Display.get_default().get_monitor(0)).get_geometry().width

    def _setup_style(self):
        screen = Gdk.Screen.get_default()
        visual = screen.get_rgba_visual()
        if visual is not None:
            self.set_visual(visual)
        self.set_app_paintable(True)
        provider = Gtk.CssProvider()
        provider.load_from_data(build_css(self.appearance))
        Gtk.StyleContext.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        stylesheet = os.path.expanduser(self.config.stylesheet)
        if os.path.exists(stylesheet):
            user = Gtk.CssProvider()
            try:
                user.load_from_path(stylesheet)
            except GLib.Error as error:
                LOG.warning("ignoring %s: %s", stylesheet, error.message)
            else:
                Gtk.StyleContext.add_provider_for_screen(screen, user, Gtk.STYLE_PROVIDER_PRIORITY_USER)

    def _build(self):
        a, l = self.appearance, self.layout
        chrome = (a.padding + a.border_width) * 2
        content = self.item_w * l.visible + l.spacing * (l.visible - 1)
        self.view_width = max(self.item_w, min(content, self.monitor_width - chrome - 2 * l.spacing))

        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        panel.get_style_context().add_class("wallpicker-panel")
        self.add(panel)

        if not self.files:
            label = Gtk.Label(label=f"No wallpapers found in {os.path.expanduser(self.config.general.directory)}")
            label.get_style_context().add_class("wallpicker-empty")
            panel.pack_start(label, False, False, 0)
            return

        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_policy(Gtk.PolicyType.EXTERNAL, Gtk.PolicyType.NEVER)
        self.scroller.set_size_request(self.view_width, self.item_h)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=l.spacing)
        side = max(0, (self.view_width - self.item_w) // 2)
        row.set_margin_start(side)
        row.set_margin_end(side)
        self.scroller.add(row)
        panel.pack_start(self.scroller, False, False, 0)

        for i in range(len(self.files)):
            area = Gtk.DrawingArea()
            area.set_size_request(self.item_w, self.item_h)
            area.surface = None
            area.connect("draw", self.on_draw, i)
            box = Gtk.EventBox()
            box.add(area)
            box.connect("button-press-event", self.on_click, i)
            row.pack_start(box, False, False, 0)
            self.items.append(area)

    def _load_order(self):
        order = [self.index]
        for distance in range(1, len(self.files)):
            for j in (self.index + distance, self.index - distance):
                if 0 <= j < len(self.files):
                    order.append(j)
        return order

    def _load_next(self, order):
        i = next(order, None)
        if i is None:
            return False
        try:
            self.items[i].surface = self.thumbnailer.surface(self.files[i])
        except (GLib.Error, OSError) as error:
            LOG.warning("cannot thumbnail %s: %s", self.files[i], error)
        self.items[i].queue_draw()
        return True

    def on_draw(self, area, cr, i):
        selected = i == self.index
        pad = self.layout.item_padding
        if selected:
            cr.set_source_rgba(*self.selection)
            round_rect(cr, 0, 0, self.item_w, self.item_h, self.appearance.item_radius)
            cr.fill()
        if area.surface is not None:
            cr.set_source_surface(area.surface, pad, pad)
            cr.paint_with_alpha(1.0 if selected else self.appearance.dim)
        else:
            cr.set_source_rgba(*self.placeholder)
            round_rect(cr, pad, pad, self.layout.thumb_width, self.layout.thumb_height, self.appearance.thumb_radius)
            cr.fill()
        return False

    def select(self, i, preview=True, animate=True):
        if not self.files:
            return
        i = max(0, min(len(self.files) - 1, i))
        previous, self.index = self.index, i
        self.items[previous].queue_draw()
        self.items[i].queue_draw()
        self._scroll_to(i, animate)
        if preview and self.config.general.live_preview:
            if self.preview_source:
                GLib.source_remove(self.preview_source)
            self.preview_source = GLib.timeout_add(self.config.general.preview_delay_ms, self._preview)

    def _preview(self):
        self.preview_source = 0
        path = self.files[self.index]
        if path != self.previewed and commands.run(self.config.commands.preview, path):
            self.previewed = path
        return False

    def _scroll_to(self, i, animate):
        adjustment = self.scroller.get_hadjustment()
        target = i * (self.item_w + self.layout.spacing)
        if self.scroll_source:
            GLib.source_remove(self.scroll_source)
            self.scroll_source = 0
        if not animate:
            GLib.idle_add(lambda: adjustment.set_value(target) and False)
            return
        start = adjustment.get_value()
        began = GLib.get_monotonic_time()

        def step():
            t = min(1.0, (GLib.get_monotonic_time() - began) / SCROLL_ANIMATION_US)
            adjustment.set_value(start + (target - start) * (1 - (1 - t) ** 3))
            if t >= 1.0:
                self.scroll_source = 0
                return False
            return True

        self.scroll_source = GLib.timeout_add(8, step)

    def on_scroll(self, _widget, event):
        step = 0
        if event.direction in (Gdk.ScrollDirection.DOWN, Gdk.ScrollDirection.RIGHT):
            step = 1
        elif event.direction in (Gdk.ScrollDirection.UP, Gdk.ScrollDirection.LEFT):
            step = -1
        elif event.direction == Gdk.ScrollDirection.SMOOTH:
            _, dx, dy = event.get_scroll_deltas()
            delta = dy if abs(dy) >= abs(dx) else dx
            step = 1 if delta > 0.3 else -1 if delta < -0.3 else 0
        if step:
            self.select(self.index + step)
        return True

    def on_click(self, _widget, event, i):
        if event.button == 1:
            if i == self.index:
                self.apply()
            else:
                self.select(i)
        elif event.button == 3:
            self.cancel()
        return True

    def on_key(self, _widget, event):
        action = self.keymap.get(Gdk.keyval_to_lower(event.keyval)) or self.keymap.get(event.keyval)
        if action == "next":
            self.select(self.index + 1)
        elif action == "previous":
            self.select(self.index - 1)
        elif action == "first":
            self.select(0)
        elif action == "last":
            self.select(len(self.files) - 1)
        elif action == "apply":
            self.apply()
        elif action == "cancel":
            self.cancel()
        return True

    def apply(self):
        if self.finished:
            return
        self.finished = True
        if self.files:
            path = self.files[self.index]
            if commands.run(self.config.commands.apply, path):
                try:
                    write_state(self.config.general.state_file, path)
                except OSError as error:
                    LOG.warning("cannot write %s: %s", self.config.general.state_file, error)
        self.get_application().quit()

    def cancel(self):
        if self.finished:
            return
        self.finished = True
        if self.original and self.previewed != self.original:
            commands.run(self.config.commands.preview, self.original)
        self.get_application().quit()


class App(Gtk.Application):
    def __init__(self, config, directory):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.config = config
        self.directory = directory
        self.window = None

    def do_activate(self):
        if self.window is not None:
            self.window.cancel()
            return
        self.window = Picker(self, self.config, self.directory)


def run(config, directory):
    return App(config, directory).run([])
