"""Cross-platform WAV playback by shelling out to whatever the OS ships with."""
from __future__ import annotations

import platform
import shutil
import subprocess
import sys


def play_wav(path: str) -> int:
    sysname = platform.system()
    if sysname == "Darwin":
        return subprocess.run(["afplay", path]).returncode
    if sysname == "Linux":
        for player, args in (("paplay", []), ("aplay", ["-q"]),
                             ("ffplay", ["-nodisp", "-autoexit", "-loglevel", "error"])):
            if shutil.which(player):
                return subprocess.run([player, *args, path]).returncode
        print("mhash: no audio player found "
              "(install pulseaudio-utils, alsa-utils, or ffmpeg)", file=sys.stderr)
        return 1
    if sysname == "Windows":
        ps = f'(New-Object Media.SoundPlayer "{path}").PlaySync();'
        return subprocess.run(["powershell", "-NoProfile", "-Command", ps]).returncode
    print(f"mhash: unsupported platform: {sysname}", file=sys.stderr)
    return 1
