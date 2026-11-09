import logging
import os
import shlex
import subprocess

LOG = logging.getLogger("wallpicker")


def build(command, path):
    if isinstance(command, str):
        return ["sh", "-c", command.replace("{path}", shlex.quote(path))]
    argv = [part.replace("{path}", path) for part in command]
    argv[0] = os.path.expanduser(argv[0])
    return argv


def run(command, path):
    argv = build(command, path)
    try:
        subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as error:
        LOG.error("could not run %s: %s", argv[0], error)
        return False
    return True
