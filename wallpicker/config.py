import os
import re
import tomllib
from dataclasses import dataclass, field, fields, replace

DEFAULT_PREVIEW = [
    "awww", "img", "{path}",
    "--transition-type", "fade",
    "--transition-duration", "0.35",
    "--transition-fps", "60",
]
DEFAULT_APPLY = [
    "awww", "img", "{path}",
    "--transition-type", "grow",
    "--transition-duration", "1",
]
POSITIONS = ("bottom", "top", "center")
COLOR_RE = re.compile(r"^#([0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def config_home():
    return os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")


def cache_home():
    return os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")


def default_config_path():
    return os.path.join(config_home(), "wallpicker", "config.toml")


@dataclass(frozen=True)
class General:
    directory: str = "~/Pictures/Wallpapers"
    recursive: bool = True
    state_file: str = field(default_factory=lambda: os.path.join(cache_home(), "wallpicker", "current"))
    live_preview: bool = True
    preview_delay_ms: int = 220
    monitor: str = "focused"


@dataclass(frozen=True)
class Commands:
    preview: object = field(default_factory=lambda: list(DEFAULT_PREVIEW))
    apply: object = field(default_factory=lambda: list(DEFAULT_APPLY))


@dataclass(frozen=True)
class Layout:
    position: str = "bottom"
    margin: int = 120
    visible: int = 5
    thumb_width: int = 288
    thumb_height: int = 162
    spacing: int = 8
    item_padding: int = 6


@dataclass(frozen=True)
class Appearance:
    background: str = "#0d1117b3"
    border: str = "#30363d"
    border_width: int = 2
    radius: int = 16
    padding: int = 16
    selection: str = "#1f6feb73"
    item_radius: int = 10
    thumb_radius: int = 8
    dim: float = 0.55
    placeholder: str = "#161b22"


@dataclass(frozen=True)
class Keys:
    next: tuple = ("Right", "Down", "l", "j", "Tab")
    previous: tuple = ("Left", "Up", "h", "k", "ISO_Left_Tab")
    first: tuple = ("Home",)
    last: tuple = ("End",)
    apply: tuple = ("Return", "KP_Enter", "space")
    cancel: tuple = ("Escape", "q")


@dataclass(frozen=True)
class Config:
    general: General = field(default_factory=General)
    commands: Commands = field(default_factory=Commands)
    layout: Layout = field(default_factory=Layout)
    appearance: Appearance = field(default_factory=Appearance)
    keys: Keys = field(default_factory=Keys)
    stylesheet: str = field(default_factory=lambda: os.path.join(config_home(), "wallpicker", "style.css"))


SECTIONS = {
    "general": General,
    "commands": Commands,
    "layout": Layout,
    "appearance": Appearance,
    "keys": Keys,
}

RANGES = {
    ("general", "preview_delay_ms"): (0, 10000),
    ("layout", "margin"): (0, 10000),
    ("layout", "visible"): (1, 50),
    ("layout", "thumb_width"): (16, 4096),
    ("layout", "thumb_height"): (16, 4096),
    ("layout", "spacing"): (0, 1000),
    ("layout", "item_padding"): (0, 1000),
    ("appearance", "border_width"): (0, 100),
    ("appearance", "radius"): (0, 1000),
    ("appearance", "padding"): (0, 1000),
    ("appearance", "item_radius"): (0, 1000),
    ("appearance", "thumb_radius"): (0, 1000),
    ("appearance", "dim"): (0.0, 1.0),
}

COLORS = {"background", "border", "selection", "placeholder"}


class ConfigError(ValueError):
    pass


def parse_color(value):
    if not isinstance(value, str) or not COLOR_RE.match(value):
        raise ConfigError(f"invalid colour {value!r}, expected #rrggbb or #rrggbbaa")
    digits = value[1:]
    channels = [int(digits[i:i + 2], 16) / 255 for i in range(0, len(digits), 2)]
    if len(channels) == 3:
        channels.append(1.0)
    return tuple(channels)


def _is_command(value):
    if isinstance(value, str):
        return bool(value.strip())
    return isinstance(value, list) and bool(value) and all(isinstance(v, str) for v in value)


def _check(section, key, default, value):
    if section == "keys":
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
            raise ConfigError(f"[keys] {key} must be a key name or a list of key names")
        return tuple(value)
    if section == "commands":
        if not _is_command(value):
            raise ConfigError(f"[commands] {key} must be a string or a non-empty list of strings")
        return value
    if isinstance(default, bool):
        if not isinstance(value, bool):
            raise ConfigError(f"[{section}] {key} must be true or false")
    elif isinstance(default, float):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigError(f"[{section}] {key} must be a number")
        value = float(value)
    elif isinstance(default, int):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(f"[{section}] {key} must be a whole number")
    elif isinstance(default, str):
        if not isinstance(value, str) or not value:
            raise ConfigError(f"[{section}] {key} must be a non-empty string")
    bounds = RANGES.get((section, key))
    if bounds and not bounds[0] <= value <= bounds[1]:
        raise ConfigError(f"[{section}] {key} must be between {bounds[0]} and {bounds[1]}")
    if section == "layout" and key == "position" and value not in POSITIONS:
        raise ConfigError(f"[layout] position must be one of {', '.join(POSITIONS)}")
    if section == "appearance" and key in COLORS:
        parse_color(value)
    return value


def apply_overrides(config, data):
    if not isinstance(data, dict):
        raise ConfigError("the config file must be a TOML table")
    updates = {}
    for section, values in data.items():
        if section == "stylesheet":
            if not isinstance(values, str) or not values:
                raise ConfigError("stylesheet must be a path")
            updates["stylesheet"] = values
            continue
        cls = SECTIONS.get(section)
        if cls is None:
            raise ConfigError(f"unknown section [{section}]")
        if not isinstance(values, dict):
            raise ConfigError(f"[{section}] must be a table")
        current = getattr(config, section)
        changes = {}
        known = {f.name: f for f in fields(cls)}
        for key, value in values.items():
            if key not in known:
                raise ConfigError(f"unknown option [{section}] {key}")
            changes[key] = _check(section, key, getattr(current, key), value)
        updates[section] = replace(current, **changes)
    return replace(config, **updates)


def load_config(path=None):
    explicit = path is not None
    path = os.path.expanduser(path) if explicit else default_config_path()
    if not os.path.exists(path):
        if explicit:
            raise ConfigError(f"config file not found: {path}")
        return Config()
    try:
        with open(path, "rb") as handle:
            data = tomllib.load(handle)
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path}: {error}") from error
    return apply_overrides(Config(), data)
