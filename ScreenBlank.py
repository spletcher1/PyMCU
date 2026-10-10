"""Screen blanking time, set from the app's settings page.

Blanking is the swayidle line in ~/.config/labwc/autostart (see docs/Pi5Setup.md, section 4):

    swayidle -w timeout 60 'wlopm --off \\*' resume 'wlopm --on \\*' &

Saving rewrites that line, so the time also applies after a reboot, and restarts swayidle so it
applies now. 0 means never blank: the line is removed and swayidle stopped.
"""
import os
import re
import subprocess

AUTOSTART = os.path.expanduser("~/.config/labwc/autostart")
SWAYIDLE_LINE = re.compile(r"^\s*swayidle\b.*$", re.MULTILINE)
OFF_COMMAND = "wlopm --off \\*"
ON_COMMAND = "wlopm --on \\*"


def ReadSeconds():
    """Blanking time in seconds from the autostart file; 0 if blanking is off."""
    try:
        with open(AUTOSTART) as f:
            line = SWAYIDLE_LINE.search(f.read())
    except OSError:
        return 0
    timeout = re.search(r"\btimeout\s+(\d+)", line.group(0)) if line else None
    return int(timeout.group(1)) if timeout else 0


def SetSeconds(seconds):
    """Saves and applies the blanking time. Returns an error message, or None."""
    try:
        with open(AUTOSTART) as f:
            text = f.read()
    except OSError as e:
        return "Can't read " + AUTOSTART + ": " + str(e)
    line = "swayidle -w timeout {} '{}' resume '{}' &".format(seconds, OFF_COMMAND, ON_COMMAND)
    if seconds <= 0:
        text = SWAYIDLE_LINE.sub("", text)
    elif SWAYIDLE_LINE.search(text):
        text = SWAYIDLE_LINE.sub(line, text, count=1)
    else:
        text = line + "\n" + text
    text = re.sub(r"\n{3,}", "\n\n", text).lstrip("\n")
    try:
        with open(AUTOSTART, "w") as f:
            f.write(text)
    except OSError as e:
        return "Can't write " + AUTOSTART + ": " + str(e)

    # Apply now: replace the running swayidle (it inherits the app's Wayland session).
    subprocess.run(["pkill", "-u", str(os.getuid()), "-x", "swayidle"], capture_output=True)
    if seconds > 0:
        try:
            subprocess.Popen(["swayidle", "-w", "timeout", str(seconds), OFF_COMMAND, "resume", ON_COMMAND],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        except OSError as e:
            return "Saved, but swayidle didn't start: " + str(e)
    return None
