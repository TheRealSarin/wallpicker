import hashlib
import os

EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".avif", ".jxl")


def list_wallpapers(directory, recursive=True):
    directory = os.path.expanduser(directory)
    if not os.path.isdir(directory):
        return []
    found = []
    if recursive:
        for root, dirs, names in os.walk(directory):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            found.extend(os.path.join(root, n) for n in names if n.lower().endswith(EXTENSIONS))
    else:
        for entry in os.scandir(directory):
            if entry.is_file() and entry.name.lower().endswith(EXTENSIONS):
                found.append(entry.path)
    return sorted(found, key=lambda p: (os.path.relpath(p, directory).lower(), p))


def read_state(path):
    try:
        with open(os.path.expanduser(path)) as handle:
            return handle.read().strip()
    except OSError:
        return ""


def write_state(path, wallpaper):
    path = os.path.expanduser(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as handle:
        handle.write(wallpaper + "\n")
    os.replace(tmp, path)


def cover_crop(src_w, src_h, dst_w, dst_h):
    scale = max(dst_w / src_w, dst_h / src_h)
    w = max(dst_w, round(src_w * scale))
    h = max(dst_h, round(src_h * scale))
    return w, h, (w - dst_w) // 2, (h - dst_h) // 2


def thumbnail_key(path, mtime_ns, width, height):
    return hashlib.sha1(f"{path}\0{mtime_ns}\0{width}x{height}".encode()).hexdigest()
