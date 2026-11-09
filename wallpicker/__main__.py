import argparse
import logging
import sys
from dataclasses import replace

from . import __version__
from .config import ConfigError, default_config_path, load_config
from .library import list_wallpapers

LOG = logging.getLogger("wallpicker")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="wallpicker",
        description="Scroll through a folder of wallpapers and preview them live on Wayland",
    )
    parser.add_argument("directory", nargs="?", help="wallpaper folder, overrides the config file")
    parser.add_argument("-c", "--config", help=f"config file (default: {default_config_path()})")
    parser.add_argument("--list", action="store_true", help="print the wallpapers that would be shown and exit")
    parser.add_argument("--check-config", action="store_true", help="validate the config file and exit")
    parser.add_argument("-v", "--verbose", action="store_true", help="log debug output")
    parser.add_argument("--version", action="version", version=f"wallpicker {__version__}")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(name)s: %(levelname)s: %(message)s",
    )
    try:
        config = load_config(args.config)
    except (ConfigError, OSError) as error:
        LOG.error("%s", error)
        return 2
    if args.directory:
        config = replace(config, general=replace(config.general, directory=args.directory))
    if args.check_config:
        print("config ok")
        return 0
    if args.list:
        for path in list_wallpapers(config.general.directory, config.general.recursive):
            print(path)
        return 0
    try:
        from .picker import run
    except (ImportError, ValueError) as error:
        LOG.error("GTK 3, gtk-layer-shell and PyGObject are required: %s", error)
        return 1
    return run(config, config.general.directory)


if __name__ == "__main__":
    sys.exit(main())
