#!/usr/bin/env bash
set -euo pipefail

repo="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
target="$HOME/.local/bin"
desktop=0

for arg in "$@"; do
    case "$arg" in
        --desktop) desktop=1 ;;
        -h|--help)
            echo "usage: install.sh [--desktop] [BIN_DIR]"
            echo "  links wallpicker into BIN_DIR (default: ~/.local/bin)"
            echo "  --desktop also installs a launcher entry for rofi, wofi, fuzzel and friends"
            exit 0
            ;;
        *) target="$arg" ;;
    esac
done

mkdir -p "$target"
ln -sf "$repo/bin/wallpicker" "$target/wallpicker"
echo "linked $target/wallpicker -> $repo/bin/wallpicker"

if [[ $desktop -eq 1 ]]; then
    apps="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
    mkdir -p "$apps"
    sed "s|^Exec=.*|Exec=$target/wallpicker|" "$repo/examples/wallpicker.desktop" > "$apps/wallpicker.desktop"
    echo "installed $apps/wallpicker.desktop"
fi

case ":$PATH:" in
    *":$target:"*) ;;
    *) echo "warning: $target is not on PATH" ;;
esac
