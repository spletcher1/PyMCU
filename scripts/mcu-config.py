#!/usr/bin/env python3
"""Checks and fixes an MCU's system setup for PyMCU, following docs/MCUSetup.md.

Run it on the MCU from the PyMCU folder with sudo. It then writes the system files directly and
sets up the files of the user who ran sudo (run without sudo, it calls sudo itself as needed):

    sudo scripts/mcu-config.py PI5            Pi 5 with the original 800x480 touch display
    sudo scripts/mcu-config.py PI5 Rotated    Pi 5 with the Touch Display 2 (portrait panel turned to landscape)
    sudo scripts/mcu-config.py PI4            Pi 4 with the original touch display and the DS3231 clock module
    (PI4 Rotated works the same way for a Pi 4 with the Touch Display 2.)

Every setting from the guide is reported as ok, fixed, added or disabled; --check reports without
changing anything. Covered: config.txt and cmdline.txt, /etc/modules, the serial console and
Bluetooth services, the user's groups, the uv environment, labwc autostart (app and screen
blanking), pcmanfm USB and desktop settings, the taskbar, labwc keyboard shortcuts, screen
orientation (a kanshi profile for the connected display in every config kanshi reads, and any
wlr-randr rotation in an autostart file disabled), hwclock and sudoers, and the Plymouth boot
splash. The splash goes into the boot images of both the Pi 4 and the Pi 5 kernels, so the card
can move between them, and each Pi's display keeps its own kanshi profile. Not covered, do by hand:
flashing the OS, desktop auto-login, timezone and hostname (raspi-config), installing uv and gh,
SSH key-only login, the user's password.

Options:
    --check   report only; exit code 1 when anything would change
    --left    Rotated profiles: the display is turned the other way (Orientation Left, transform 270)
    --force   run even when the Pi model does not match the profile

config.txt and cmdline.txt are backed up next to themselves (*.mcu-config.bak) the first time
they are changed. Test hook: with MCU_CONFIG_PREFIX=<dir> every system path is taken under <dir>,
MCU_CONFIG_HOME=<dir> replaces the user's home, and no commands are run, only shown.
"""
import argparse
import filecmp
import getpass
import glob
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile

PREFIX = os.environ.get("MCU_CONFIG_PREFIX", "")
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONFIG_TXT = "/boot/firmware/config.txt"
CMDLINE_TXT = "/boot/firmware/cmdline.txt"
MODULES = "/etc/modules"
OS_RELEASE = "/etc/os-release"
MODEL_FILE = "/proc/device-tree/model"
SUDOERS_FILE = "/etc/sudoers.d/pymcu"
HWCLOCK = "/usr/sbin/hwclock"
PLYMOUTH_THEMES = "/usr/share/plymouth/themes"
FIRMWARE_DIR = "/boot/firmware"
# The boot image of each 64-bit kernel and the Pi that boots it. A card holds both, so it can
# move between a Pi 4 and a Pi 5, and the splash must be in both.
BOOT_IMAGES = {"initramfs8": "Pi 4", "initramfs_2712": "Pi 5"}
DRM_DIR = "/sys/class/drm"
# Files whose commands run when the desktop starts, where a wlr-randr rotation would override kanshi.
AUTOSTART_FILES = ["~/.config/labwc/autostart", "/etc/xdg/labwc/autostart",
                   "~/.config/autostart/*.desktop", "/etc/xdg/autostart/*.desktop"]
ROTATION_RE = re.compile(r"\bwlr-randr\b.*--transform")
# kanshi -c FILE or --config FILE: that kanshi reads FILE instead of ~/.config/kanshi/config.
KANSHI_CONFIG_RE = re.compile(r"\bkanshi\b.*?\s(?:-c|--config)(?:\s+|=)\"?([^\"\s&;]+)")
XDG_PCMANFM = "/etc/xdg/pcmanfm/default"

GROUPS = ["gpio", "i2c", "dialout"]
QUIET_BOOT = ["logo.nologo", "vt.global_cursor_default=0", "loglevel=3"]
SWAYIDLE_LINE = "swayidle -w timeout 60 'wlopm --off \\*' resume 'wlopm --on \\*' &"
KEYBINDS = [
    ("C-A-t", '<keybind key="C-A-t"><action name="None" /></keybind>'),
    ("W-Return", '<keybind key="W-Return"><action name="None" /></keybind>'),
    ("Super_L", '<keybind key="Super_L" onRelease="yes"><action name="None" /></keybind>'),
    ("A-F2", '<keybind key="A-F2"><action name="None" /></keybind>'),
    ("A-F3", '<keybind key="A-F3"><action name="None" /></keybind>'),
    ("A-F4", '<keybind key="A-F4"><action name="None" /></keybind>'),
    ("A-Tab", '<keybind key="A-Tab"><action name="None" /></keybind>'),
    ("A-space", '<keybind key="A-space"><action name="None" /></keybind>'),
]
PANEL = {
    "widgets_left": "spacing4",
    "widgets_right": "tray power spacing2 connect spacing2 bluetooth spacing2 netman spacing2 "
                     "volumepulse spacing2 clock spacing2 batt spacing2 squeek",
    "notify": "false",
}
DESKTOP = {"wallpaper_mode": "color", "desktop_bg": "#000000000000",
           "show_documents": "0", "show_trash": "0", "show_mounts": "0"}
VOLUME = {"mount_on_startup": "1", "mount_removable": "1", "autorun": "0"}

# What each model needs, per docs/MCUSetup.md sections 1 and 7. config_remove lists line starts
# that belong to the other model and are commented out if found.
MODELS = {
    "PI4": dict(model="Raspberry Pi 4", section="pi4",
                config_add=["dtparam=i2c_arm=on", "enable_uart=1", "dtoverlay=disable-bt",
                            "dtoverlay=i2c-rtc,ds3231"],
                config_remove=["dtparam=rtc_bbat_vchg"],
                cmdline_remove=["console=serial0", "console=ttyAMA0"],
                services_off=["hciuart.service", "serial-getty@ttyAMA0.service"]),
    "PI5": dict(model="Raspberry Pi 5", section="pi5",
                config_add=["dtparam=i2c_arm=on", "dtparam=uart0=on", "dtparam=rtc_bbat_vchg=3000000"],
                config_remove=["dtoverlay=i2c-rtc"],
                cmdline_remove=[],
                services_off=["serial-getty@ttyAMA0.service"]),
}


# ---------------------------------------------------------------- reporting and file access

class Report:
    def __init__(self, check):
        self.check = check
        self.oks = 0
        self.changes = 0
        self.warnings = 0
        self.failures = 0
        self.reboot = False
        self.rebuild = False   # the boot images need rebuilding (RebuildBootImages)

    VERBS = {"added": "add", "fixed": "fix", "removed": "remove", "disabled": "disable", "installed": "install"}

    def section(self, title):
        print("\n" + title)

    def line(self, label, msg):
        print("  " + label.ljust(14) + msg)

    def ok(self, msg):
        self.oks += 1
        self.line("ok", msg)

    def change(self, verb, msg):
        """verb is the past tense: added, fixed, removed, disabled, installed."""
        self.changes += 1
        self.line("would " + self.VERBS[verb] if self.check else verb, msg)

    def warn(self, msg):
        self.warnings += 1
        self.line("WARNING", msg)

    def fail(self, msg):
        self.failures += 1
        self.line("FAILED", msg)


def SysPath(path):
    return PREFIX + path


def IsRoot():
    return hasattr(os, "geteuid") and os.geteuid() == 0


def TargetUser():
    user = os.environ.get("MCU_CONFIG_USER")
    if not user and IsRoot():
        user = os.environ.get("SUDO_USER")
    return user or getpass.getuser()


def UserHome(user):
    home = os.environ.get("MCU_CONFIG_HOME")
    if home:
        return home
    try:
        import pwd
        return pwd.getpwnam(user).pw_dir
    except (ImportError, KeyError):
        return os.path.expanduser("~")


def Run(cmd, root=False, cwd=None):
    """Runs a command, through sudo when root=True and not already root. In test mode the command
    is only shown. Returns (exit code, stdout, stderr)."""
    if PREFIX:
        print("           (would run: " + " ".join(cmd) + ")")
        return 0, "", ""
    if root and not IsRoot():
        cmd = ["sudo"] + cmd
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    except OSError as e:
        return 127, "", str(e)
    return r.returncode, r.stdout, r.stderr


def ReadText(path, system=True):
    """Text of a file, or None if it doesn't exist. System files are taken under the test prefix,
    and root-only ones (sudoers) are read through sudo."""
    full = SysPath(path) if system else path
    try:
        with open(full, encoding="utf-8", errors="replace") as f:
            return f.read()
    except FileNotFoundError:
        return None
    except PermissionError:
        if PREFIX:
            raise
        code, out, err = Run(["cat", full], root=True)
        return out if code == 0 else None


def WriteSystem(path, text, mode=None, backup=False):
    """Writes a system file as root. With backup=True the original is kept once as
    <file>.mcu-config.bak."""
    full = SysPath(path)
    if PREFIX or IsRoot():
        if backup and os.path.exists(full) and not os.path.exists(full + ".mcu-config.bak"):
            shutil.copyfile(full, full + ".mcu-config.bak")  # content only: /boot/firmware is FAT
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        if mode is not None and not PREFIX:
            os.chmod(full, mode)
        return
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", newline="\n") as tmp:
        tmp.write(text)
    try:
        if backup:
            Run(["cp", "-n", full, full + ".mcu-config.bak"], root=True)
        Run(["mkdir", "-p", os.path.dirname(full)], root=True)
        code, out, err = Run(["cp", tmp.name, full], root=True)
        if code != 0:
            raise OSError("can't write " + full + ": " + err.strip())
        if mode is not None:
            Run(["chmod", oct(mode)[2:], full], root=True)
    finally:
        os.unlink(tmp.name)


def WriteUser(path, text, user):
    """Writes one of the user's files. When run through sudo, the file and its folder are given
    back to the user."""
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    if IsRoot() and os.environ.get("SUDO_USER") and not PREFIX:
        Run(["chown", user + ":" + user, folder, path])


def SetIniKeys(text, section, keys):
    """Sets key=value lines inside [section], adding the section if missing and keeping everything
    else. Returns (new text, list of (status, message)) with one entry per key."""
    lines = text.splitlines()
    header = "[" + section + "]"
    start = next((i for i, l in enumerate(lines) if l.strip() == header), None)
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(header)
        start = len(lines) - 1
    end = next((i for i in range(start + 1, len(lines)) if lines[i].strip().startswith("[")), len(lines))
    results = []
    for key, value in keys.items():
        want = key + "=" + value
        found = [i for i in range(start + 1, end)
                 if not lines[i].strip().startswith("#") and lines[i].split("=")[0].strip() == key]
        if found:
            i = found[-1]
            if lines[i].strip() == want:
                results.append(("ok", want))
            else:
                results.append(("fixed", want + "  (was " + lines[i].strip() + ")"))
                lines[i] = want
        else:
            results.append(("added", want))
            lines.insert(end, want)
            end += 1
    return "\n".join(lines) + "\n", results


def ApplyIni(rep, path, section, keys, template, user, label):
    """Brings one ini-style user file into line, starting from the system template when the
    user's copy doesn't exist yet."""
    text = ReadText(path, system=False)
    created = text is None
    if created:
        text = ReadText(template) or ""
    new, results = SetIniKeys(text, section, keys)
    for status, msg in results:
        if status == "ok":
            rep.ok(label + ": " + msg)
        else:
            rep.change(status, label + ": " + msg)
    if new != text or created:
        if created:
            rep.change("added", path + ("  (copied from " + template + ")" if ReadText(template) else ""))
        if not rep.check:
            WriteUser(path, new, user)


# ---------------------------------------------------------------- checks

def CheckModelAndOS(prof, rep, force):
    rep.section("Board and OS")
    model = ReadText(MODEL_FILE)
    if model is None:
        msg = "can't read " + MODEL_FILE + ": this doesn't look like a Raspberry Pi"
        if force or rep.check:
            rep.warn(msg)
        else:
            rep.fail(msg + " (use --force to run anyway)")
            return False
    else:
        model = model.strip("\0\n ")
        if prof["model"] in model:
            rep.ok(model)
        elif force:
            rep.warn(model + " does not match profile " + prof["name"] + " (continuing with --force)")
        else:
            rep.fail(model + " does not match profile " + prof["name"] + " (use --force to run anyway)")
            return False
    release = ReadText(OS_RELEASE) or ""
    m = re.search(r'^VERSION_CODENAME=\"?(\w+)', release, re.M)
    codename = m.group(1) if m else "unknown"
    if codename == "trixie":
        rep.ok("Raspberry Pi OS Trixie")
    else:
        rep.warn("OS codename is " + codename + "; the guide is for Trixie")
    host = platform.node()
    if "MCU" in host:
        rep.ok("hostname " + host + " contains MCU")
    else:
        rep.warn("hostname " + host + " does not contain MCU: the app will not use the hardware. "
                 "Fix with: sudo raspi-config nonint do_hostname FLICMCU")
    return True


SECTION_RE = re.compile(r"^\[(.+)\]$")


def ConfigKey(line):
    """What a config.txt line sets: dtparam=uart0, dtoverlay=disable-bt, enable_uart."""
    line = line.strip()
    if line.startswith("dtparam="):
        return "dtparam=" + line[8:].split("=")[0].split(",")[0].strip()
    if line.startswith("dtoverlay="):
        return "dtoverlay=" + line[10:].split(",")[0].strip()
    return line.split("=")[0].strip()


def CheckConfigTxt(prof, rep):
    rep.section("config.txt  (" + CONFIG_TXT + ")")
    text = ReadText(CONFIG_TXT)
    if text is None:
        rep.fail("not found")
        return
    lines = text.splitlines()
    applicable = {"", "all", prof["section"]}
    section = ""
    active = {}      # key -> index of the last active line in a section that applies to this model
    commented = {}   # key -> index of a commented-out line, e.g. "#dtparam=i2c_arm=on"
    anywhere = {}    # key -> indices of active lines in any section
    for i, raw in enumerate(lines):
        s = raw.strip()
        m = SECTION_RE.match(s)
        if m:
            section = m.group(1).strip().lower()
            continue
        if not s:
            continue
        if s.startswith("#"):
            body = s.lstrip("#").strip()
            if "=" in body and " " not in body and section in applicable:
                commented.setdefault(ConfigKey(body), i)
            continue
        key = ConfigKey(s)
        anywhere.setdefault(key, []).append(i)
        if section in applicable:
            active[key] = i
    changed = False
    to_add = []
    for want in prof["config_add"]:
        key = ConfigKey(want)
        if key in active:
            if lines[active[key]].strip() == want:
                rep.ok(want)
            else:
                rep.change("fixed", want + "  (was " + lines[active[key]].strip() + ")")
                lines[active[key]] = want
                changed = True
        elif key in commented:
            rep.change("added", want + "  (uncommented)")
            lines[commented[key]] = want
            changed = True
        else:
            rep.change("added", want)
            to_add.append(want)
    for start in prof["config_remove"]:
        hits = [i for idxs in anywhere.values() for i in idxs if lines[i].strip().startswith(start)]
        if not hits:
            rep.ok("no " + start + " line")
        for i in hits:
            rep.change("disabled", lines[i].strip() + "  (not for this model)")
            lines[i] = "#" + lines[i].strip() + "   (disabled by mcu-config " + prof["name"] + ")"
            changed = True
    if to_add:
        last_section = ""
        for raw in lines:
            m = SECTION_RE.match(raw.strip())
            if m:
                last_section = m.group(1).strip().lower()
        if lines and lines[-1].strip():
            lines.append("")
        if last_section != "all":
            lines.append("[all]")
        lines.append("# PyMCU (scripts/mcu-config.py " + prof["name"] + ")")
        lines.extend(to_add)
        changed = True
    if changed:
        rep.reboot = True
        if not rep.check:
            WriteSystem(CONFIG_TXT, "\n".join(lines) + "\n", backup=True)


def CheckCmdline(prof, rep):
    rep.section("cmdline.txt  (" + CMDLINE_TXT + ")")
    text = ReadText(CMDLINE_TXT)
    if text is None:
        rep.fail("not found")
        return
    tokens = text.split()
    new = []
    for t in tokens:
        if any(t.startswith(start) for start in prof["cmdline_remove"]):
            rep.change("removed", t + "  (a login console would share the DFM port)")
        else:
            new.append(t)
    for start in prof["cmdline_remove"]:
        if not any(t.startswith(start) for t in tokens):
            rep.ok("no " + start)
    for want in ["quiet", "splash"] + QUIET_BOOT:
        key = want.split("=")[0]
        same_key = [i for i, t in enumerate(new) if t.split("=")[0] == key]
        note = "  (quieter boot)" if want in QUIET_BOOT else "  (boot splash)"
        if same_key and new[same_key[-1]] == want:
            rep.ok(want + note)
        elif same_key:
            rep.change("fixed", want + "  (was " + new[same_key[-1]] + ")")
            new[same_key[-1]] = want
        else:
            rep.change("added", want + note)
            new.append(want)
    if new != tokens:
        rep.reboot = True
        if not rep.check:
            WriteSystem(CMDLINE_TXT, " ".join(new) + "\n", backup=True)


def CheckModules(rep):
    rep.section("Kernel modules  (" + MODULES + ")")
    text = ReadText(MODULES) or ""
    if any(l.strip() == "i2c-dev" for l in text.splitlines()):
        rep.ok("i2c-dev")
        return
    rep.change("added", "i2c-dev")
    if not rep.check:
        WriteSystem(MODULES, text.rstrip("\n") + ("\n" if text.strip() else "") + "i2c-dev\n")


def CheckServices(prof, rep):
    rep.section("Services")
    if PREFIX:
        rep.ok("not checked in test mode: " + ", ".join(prof["services_off"]))
        return
    for unit in prof["services_off"]:
        code, enabled, err = Run(["systemctl", "is-enabled", unit])
        code2, active, err2 = Run(["systemctl", "is-active", unit])
        enabled, active = enabled.strip(), active.strip()
        if enabled in ("enabled", "enabled-runtime", "linked", "alias") or active == "active":
            rep.change("disabled", unit + "  (was " + (enabled or "?") + ", " + (active or "?") + ")")
            if not rep.check:
                Run(["systemctl", "disable", "--now", unit], root=True)
        else:
            rep.ok(unit + " is " + (enabled if code == 0 else "not installed"))


def CheckGroups(rep, user):
    rep.section("Groups of user " + user)
    if PREFIX:
        rep.ok("not checked in test mode: " + ", ".join(GROUPS))
        return
    code, out, err = Run(["id", "-nG", user])
    groups = set(out.split())
    for g in GROUPS:
        if g in groups:
            rep.ok(g)
        else:
            rep.change("added", g + "  (takes effect at the next login)")
            rep.reboot = True
            if not rep.check:
                Run(["usermod", "-aG", g, user], root=True)


def CheckAppEnvironment(rep, home, user):
    rep.section("App environment  (" + APP_DIR + ")")
    uv = os.path.join(home, ".local", "bin", "uv")
    if os.path.exists(uv):
        rep.ok("uv at " + uv)
    else:
        rep.warn("uv not found at " + uv + ". Install: curl -LsSf https://astral.sh/uv/install.sh | sh")
    venv = os.path.join(APP_DIR, ".venv")
    if os.path.isdir(venv):
        rep.ok("uv environment " + venv)
    elif os.path.exists(uv):
        rep.change("added", "uv environment (uv sync; needs the network)")
        if not rep.check:
            # As the user, so the environment isn't owned by root when run through sudo.
            as_user = ["sudo", "-u", user, "-H"] if IsRoot() and os.environ.get("SUDO_USER") else []
            code, out, err = Run(as_user + [uv, "sync"], cwd=APP_DIR)
            if code != 0:
                rep.fail("uv sync: " + err.strip()[-300:])
    else:
        rep.warn("no uv environment yet: run uv sync once uv is installed")
    script = os.path.join(APP_DIR, "RunMCU.sh")
    if not os.path.exists(script):
        rep.fail(script + " missing")
    elif os.name == "nt" or os.access(script, os.X_OK):
        rep.ok("RunMCU.sh is executable")
    else:
        rep.change("fixed", "RunMCU.sh made executable")
        if not rep.check:
            os.chmod(script, 0o755)
    for tool in ("swayidle", "wlopm"):
        if PREFIX or shutil.which(tool):
            rep.ok(tool + (" (not checked in test mode)" if PREFIX else " installed"))
        else:
            rep.warn(tool + " not installed: sudo apt install " + tool)


def CheckAutostart(rep, home, user):
    path = os.path.join(home, ".config", "labwc", "autostart")
    rep.section("labwc autostart  (" + path + ")")
    text = ReadText(path, system=False) or ""
    lines = text.splitlines()
    run_line = os.path.join(APP_DIR, "RunMCU.sh") + " &"
    changed = False
    hits = [i for i, l in enumerate(lines) if "RunMCU.sh" in l and not l.strip().startswith("#")]
    if hits and lines[hits[-1]].strip() == run_line:
        rep.ok(run_line)
    elif hits:
        rep.change("fixed", run_line + "  (was " + lines[hits[-1]].strip() + ")")
        lines[hits[-1]] = run_line
        changed = True
    else:
        rep.change("added", run_line)
        lines.append(run_line)
        changed = True
    idle = [l for l in lines if l.strip().startswith("swayidle") and not l.strip().startswith("#")]
    if idle:
        rep.ok(idle[-1].strip() + "  (the app adjusts the timeout)")
    else:
        rep.change("added", SWAYIDLE_LINE)
        lines.insert(0, SWAYIDLE_LINE)
        changed = True
    if changed and not rep.check:
        WriteUser(path, "\n".join(lines) + "\n", user)


def CheckDesktop(rep, home, user):
    rep.section("USB mounting and desktop  (~/.config/pcmanfm/default)")
    folder = os.path.join(home, ".config", "pcmanfm", "default")
    ApplyIni(rep, os.path.join(folder, "pcmanfm.conf"), "volume", VOLUME,
             XDG_PCMANFM + "/pcmanfm.conf", user, "pcmanfm.conf [volume]")
    for n in ("0", "1"):
        name = "desktop-items-" + n + ".conf"
        ApplyIni(rep, os.path.join(folder, name), "*", DESKTOP, XDG_PCMANFM + "/" + name, user, name)
    rep.section("Taskbar  (~/.config/wf-panel-pi/wf-panel-pi.ini)")
    ApplyIni(rep, os.path.join(home, ".config", "wf-panel-pi", "wf-panel-pi.ini"), "panel", PANEL,
             "/etc/xdg/wf-panel-pi/wf-panel-pi.ini", user, "wf-panel-pi.ini [panel]")


def CheckKeybinds(rep, home, user):
    path = os.path.join(home, ".config", "labwc", "rc.xml")
    rep.section("Keyboard shortcuts  (" + path + ")")
    text = ReadText(path, system=False)
    if text is None:
        text = '<?xml version="1.0"?>\n<labwc_config>\n</labwc_config>\n'
        rep.change("added", path)
    missing = []
    for key, line in KEYBINDS:
        if re.search(r'<keybind\s+key="' + re.escape(key) + '"', text):
            rep.ok(key + " unbound")
        else:
            rep.change("added", key + " unbound")
            missing.append(line)
    if not missing:
        return
    block = "\n".join("    " + l for l in missing)
    if "</keyboard>" in text:
        text = text.replace("</keyboard>", block.lstrip() + "\n  </keyboard>", 1)
    elif "</labwc_config>" in text:
        text = text.replace("</labwc_config>", "  <keyboard>\n" + block + "\n  </keyboard>\n</labwc_config>", 1)
    else:
        rep.fail("no </labwc_config> in " + path + "; add the <keyboard> block from the guide by hand")
        return
    print("           (applies after: kill -HUP $(pgrep -x labwc), or a reboot)")
    if not rep.check:
        WriteUser(path, text, user)


def OutputName(line):
    """The display a kanshi output line is for: DSI-1 in 'output DSI-1 enable transform 90'."""
    m = re.match(r'\s*output\s+(?:"([^"]*)"|(\S+))', line)
    return (m.group(1) or m.group(2)) if m else ""


def ConnectedDsiOutputs():
    names = []
    for status in sorted(glob.glob(SysPath(DRM_DIR) + "/card*-DSI-*/status")):
        if (ReadText(status, system=False) or "").strip() == "connected":
            names.append(os.path.basename(os.path.dirname(status)).split("-", 1)[1])
    return names


def AutostartFiles(home):
    """The autostart files that exist, as (path, system). A system path is without the test prefix."""
    files = []
    for pattern in AUTOSTART_FILES:
        if pattern.startswith("~/"):
            files += [(p, False) for p in sorted(glob.glob(os.path.join(home, pattern[2:])))]
        else:
            files += [(p[len(PREFIX):], True) for p in sorted(glob.glob(SysPath(pattern)))]
    return files


def KanshiConfigFiles(home):
    """The config files kanshi reads, as (path, system): ~/.config/kanshi/config, and any file an
    autostart line starts kanshi with instead (kanshi -c FILE)."""
    configs = [(os.path.join(home, ".config", "kanshi", "config"), False)]
    for path, system in AutostartFiles(home):
        for line in (ReadText(path, system=system) or "").splitlines():
            m = None if line.strip().startswith("#") else KANSHI_CONFIG_RE.search(line)
            if not m:
                continue
            config = m.group(1)
            for start in ("~/", "$HOME/", "${HOME}/"):
                if config.startswith(start):
                    config = os.path.join(home, config[len(start):])
                    break
            entry = (config, not config.startswith(home))
            if entry not in configs:
                configs.append(entry)
    return configs


def CheckOrientation(prof, rep, home, user):
    """Gives the connected display a kanshi profile with the profile's orientation, in every file
    kanshi reads. The profile is written even for normal, so that kanshi turns the display back at
    login whatever turned it before."""
    for n, (path, system) in enumerate(KanshiConfigFiles(home)):
        CheckKanshiConfig(prof, rep, path, system, user, default=n == 0)


def CheckKanshiConfig(prof, rep, path, system, user, default):
    rep.section("Screen orientation  (" + path + (", as written by Screen Configuration)" if default
                                                  else ", which an autostart line starts kanshi with)"))
    want = prof["transform"]
    outputs = ConnectedDsiOutputs()
    if not outputs:
        # Lines for the Pi 4's and the Pi 5's displays can share the file: without knowing which
        # display this is, none of them is changed.
        rep.warn("no connected DSI display found under " + DRM_DIR + ", so the orientation isn't checked")
        return
    text = ReadText(path, system=system)
    lines = text.splitlines() if text is not None else []
    output_lines = [i for i, l in enumerate(lines) if re.match(r"\s*output\s", l)]
    # A Pi 4 and a Pi 5 can name their display differently. A line for a display that isn't
    # connected is the other model's: kanshi skips it here, and it is kept for when the card goes back.
    dsi_lines = [i for i in output_lines if OutputName(lines[i]) in outputs]
    for i in output_lines:
        name = OutputName(lines[i])
        if i not in dsi_lines and "dsi" in name.lower():
            rep.ok(lines[i].strip() + "  (" + name + " isn't connected: kept for the Pi it belongs to)")
    if not dsi_lines and len(output_lines) == 1 and "dsi" not in OutputName(lines[output_lines[0]]).lower():
        dsi_lines = output_lines   # the display named another way, such as output *
    changed = False
    for i in dsi_lines:
        m = re.search(r"\btransform\s+(\S+)", lines[i])
        current = m.group(1) if m else "normal"
        if current == want:
            rep.ok(lines[i].strip())
            continue
        rep.change("fixed", "transform " + want + "  (was " + current + "): " + lines[i].strip())
        if m:
            lines[i] = lines[i][:m.start()] + "transform " + want + lines[i][m.end():]
        else:
            lines[i] = lines[i].rstrip() + " transform " + want
        changed = True
    if not dsi_lines:
        rep.change("added", "profile with output " + outputs[0] + " transform " + want)
        if lines and lines[-1].strip():
            lines.append("")
        lines += ["profile {", "\toutput " + outputs[0] + " enable transform " + want, "}"]
        changed = True
    if changed:
        print("           (applies at the next login, or: kanshictl reload)")
        if rep.check:
            return
        if system:
            WriteSystem(path, "\n".join(lines) + "\n")
        else:
            WriteUser(path, "\n".join(lines) + "\n", user)


def CheckOtherRotation(prof, rep, home, user):
    """Disables rotation set outside kanshi: a wlr-randr --transform command in an autostart file
    runs alongside kanshi at login and can win, leaving the screen turned whatever the profile.
    Shell lines are commented out; a .desktop entry gets Hidden=true. System files are backed up
    once as <file>.mcu-config.bak."""
    rep.section("Screen rotation outside kanshi  (autostart files)")
    found = False
    for path, system in AutostartFiles(home):
        text = ReadText(path, system=system) or ""
        lines = text.splitlines()
        hits = [i for i, l in enumerate(lines) if not l.strip().startswith("#") and ROTATION_RE.search(l)]
        desktop = path.endswith(".desktop")
        if not hits or (desktop and re.search(r"^\s*Hidden\s*=\s*true\s*$", text, re.M | re.I)):
            continue
        found = True
        for i in hits:
            rep.change("disabled", path + " line " + str(i + 1) + ": " + lines[i].strip()
                       + "  (the orientation comes from kanshi)")
        if desktop:
            new = SetIniKeys(text, "Desktop Entry", {"Hidden": "true"})[0]
        else:
            for i in hits:
                lines[i] = "#" + lines[i].strip() + "   (disabled by mcu-config " + prof["name"] + ")"
            new = "\n".join(lines) + "\n"
        print("           (applies at the next login)")
        if rep.check:
            continue
        if system:
            WriteSystem(path, new, backup=True)
        else:
            WriteUser(path, new, user)
    if not found:
        rep.ok("no wlr-randr rotation in the autostart files")


def CheckClockAndSudo(rep, user):
    rep.section("Clock tool and sudo rights")
    if os.path.exists(SysPath(HWCLOCK)):
        rep.ok("hwclock installed")
    else:
        rep.change("installed", "util-linux-extra (hwclock; needs the network)")
        if not rep.check:
            code, out, err = Run(["apt-get", "install", "-y", "util-linux-extra"], root=True)
            if code != 0:
                rep.fail("apt-get: " + err.strip()[-300:])
    want = user + " ALL=(root) NOPASSWD: /usr/sbin/shutdown, /usr/bin/date, /usr/sbin/hwclock\n"
    current = ReadText(SUDOERS_FILE)
    if current == want:
        rep.ok(SUDOERS_FILE)
        return
    rep.change("fixed" if current else "added", SUDOERS_FILE + ": " + want.strip())
    if rep.check:
        return
    if not PREFIX:
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".sudoers", encoding="utf-8") as tmp:
            tmp.write(want)
        try:
            code, out, err = Run(["visudo", "-cf", tmp.name], root=True)
        finally:
            os.unlink(tmp.name)
        if code != 0:
            rep.fail("visudo rejected the sudoers line: " + (out + err).strip())
            return
    WriteSystem(SUDOERS_FILE, want, mode=0o440)


def CopyTree(src, dst):
    if PREFIX or IsRoot():
        shutil.copytree(src, dst)
    else:
        Run(["cp", "-r", src, dst], root=True)


def Remove(path):
    if PREFIX or IsRoot():
        if os.path.exists(path):
            os.remove(path)
    else:
        Run(["rm", "-f", path], root=True)


def CheckSplash(prof, rep):
    rep.section("Boot splash  (Plymouth theme flic, image " + prof["splash"] + ")")
    themes = SysPath(PLYMOUTH_THEMES)
    pix, flic = os.path.join(themes, "pix"), os.path.join(themes, "flic")
    image = os.path.join(APP_DIR, "images", prof["splash"])
    if not os.path.isdir(pix):
        rep.warn("Plymouth theme pix not found at " + pix + "; splash skipped")
        return
    if not os.path.exists(image):
        rep.fail(image + " missing")
        return
    changed = False
    if os.path.isdir(flic) and os.path.exists(os.path.join(flic, "flic.plymouth")):
        rep.ok("theme flic installed")
    else:
        rep.change("added", "theme flic (copy of pix)")
        changed = True
        if not rep.check:
            if not os.path.isdir(flic):
                CopyTree(pix, flic)
            plymouth = ReadText(os.path.join(pix, "pix.plymouth"), system=False) or ""
            plymouth = re.sub(r"^Name=pix", "Name=flic", plymouth, flags=re.M)
            plymouth = re.sub(r"^Description=.*", "Description=FLIC MCU splash", plymouth, flags=re.M)
            plymouth = plymouth.replace("themes/pix", "themes/flic").replace("pix.script", "flic.script")
            WriteSystem(PLYMOUTH_THEMES + "/flic/flic.plymouth", plymouth, mode=0o644)
            WriteSystem(PLYMOUTH_THEMES + "/flic/flic.script",
                        ReadText(os.path.join(pix, "pix.script"), system=False) or "", mode=0o644)
            Remove(os.path.join(flic, "pix.plymouth"))
            Remove(os.path.join(flic, "pix.script"))
    splash = os.path.join(flic, "splash.png")
    if os.path.exists(splash) and filecmp.cmp(image, splash, shallow=False):
        rep.ok("splash.png is " + prof["splash"])
    else:
        rep.change("fixed" if os.path.exists(splash) else "added", "splash.png from " + image)
        changed = True
        if not rep.check:
            if PREFIX or IsRoot():
                shutil.copyfile(image, splash)
            else:
                Run(["cp", image, splash], root=True)
    if PREFIX:
        rep.ok("default theme not checked in test mode")
        current = "flic"
    else:
        code, current, err = Run(["plymouth-set-default-theme"])
        if code != 0:
            rep.warn("plymouth-set-default-theme not available; splash not activated")
            return
    if current.strip() == "flic":
        if not PREFIX:
            rep.ok("default theme is flic")
    else:
        rep.change("fixed", "default theme flic  (was " + (current.strip() or "?") + ")")
        changed = True
        if not rep.check:
            # Without -R, which would rebuild one kernel's boot image only: RebuildBootImages does all.
            code, out, err = Run(["plymouth-set-default-theme", "flic"], root=True)
            if code != 0:
                rep.fail("plymouth-set-default-theme flic: " + (out + err).strip()[-300:])
                return
    if changed:
        rep.rebuild = True
        return
    stale = StaleBootImages()
    for image in stale:
        rep.change("fixed", "splash in " + image + " (the " + BOOT_IMAGES[image] + " boot image): "
                   "it was built before splash.png changed")
    if stale:
        rep.rebuild = True
    else:
        rep.ok("the boot images have this splash")


def StaleBootImages():
    """The boot images built before splash.png last changed, which still show an older splash."""
    splash = SysPath(PLYMOUTH_THEMES + "/flic/splash.png")
    if not os.path.exists(splash):
        return []
    images = [(name, SysPath(FIRMWARE_DIR + "/" + name)) for name in BOOT_IMAGES]
    return [name for name, path in images
            if os.path.exists(path) and os.path.getmtime(path) < os.path.getmtime(splash)]


def RebuildBootImages(rep):
    """Rebuilds every kernel's boot image once, for the changes found above. plymouth-set-default-
    theme -R and a plain update-initramfs -u rebuild only the highest-numbered kernel's, which
    leaves the other Pi model's image with the old splash."""
    if not rep.rebuild:
        return
    rep.section("Boot images  (" + ", ".join(FIRMWARE_DIR + "/" + name for name in BOOT_IMAGES) + ")")
    rep.line("would rebuild" if rep.check else "rebuilding", "all of them (update-initramfs -u -k all, about a minute each)")
    rep.reboot = True
    if rep.check:
        return
    code, out, err = Run(["update-initramfs", "-u", "-k", "all"], root=True)
    if code != 0:
        rep.fail("update-initramfs -u -k all: " + (out + err).strip()[-300:])
        return
    if not PREFIX:
        for image in StaleBootImages():
            rep.warn(image + " is still older than splash.png: is the " + BOOT_IMAGES[image]
                     + " kernel installed (dpkg -l 'linux-image-*'), and is the clock right?")


# ---------------------------------------------------------------- main

def ParseProfile(words, left):
    key = re.sub(r"[^A-Z0-9]", "", " ".join(words).upper())
    model = key[:3]
    rotated = key[3:] in ("ROTATED", "ROT")
    if model not in MODELS or (key[3:] and not rotated):
        print("Unknown profile " + " ".join(words) + ". Use PI4, PI5, PI4 Rotated or PI5 Rotated.", file=sys.stderr)
        sys.exit(2)
    prof = dict(MODELS[model])
    prof["name"] = model + ("-Rotated" if rotated else "")
    if rotated:
        prof["transform"] = "270" if left else "90"
        prof["splash"] = "MCU_Rotated_Left.png" if left else "MCU_Rotated.png"
    else:
        prof["transform"] = "normal"
        prof["splash"] = "MCU.png"
    return prof


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("profile", nargs="+", help="PI4, PI5, PI4 Rotated or PI5 Rotated")
    parser.add_argument("--check", action="store_true", help="report only, change nothing")
    parser.add_argument("--left", action="store_true", help="rotated display turned the other way (transform 270)")
    parser.add_argument("--force", action="store_true", help="run even if the Pi model doesn't match")
    args = parser.parse_args()
    prof = ParseProfile(args.profile, args.left)
    user = TargetUser()
    home = UserHome(user)
    rep = Report(args.check)
    print("PyMCU setup check for profile " + prof["name"] + ", user " + user + ", app folder " + APP_DIR
          + (" (check only)" if args.check else "") + (" [test prefix " + PREFIX + "]" if PREFIX else ""))
    if not CheckModelAndOS(prof, rep, args.force):
        sys.exit(2)
    CheckConfigTxt(prof, rep)
    CheckCmdline(prof, rep)
    CheckModules(rep)
    CheckServices(prof, rep)
    CheckGroups(rep, user)
    CheckAppEnvironment(rep, home, user)
    CheckAutostart(rep, home, user)
    CheckDesktop(rep, home, user)
    CheckKeybinds(rep, home, user)
    CheckOrientation(prof, rep, home, user)
    CheckOtherRotation(prof, rep, home, user)
    CheckClockAndSudo(rep, user)
    CheckSplash(prof, rep)
    RebuildBootImages(rep)
    print("\nSummary: {} ok, {} {}, {} warnings, {} failed".format(
        rep.oks, rep.changes, "would change" if args.check else "changed", rep.warnings, rep.failures))
    if rep.reboot:
        print("Reboot to apply the config.txt, cmdline.txt, group or splash changes." if not args.check
              else "A reboot will be needed after these changes.")
    if rep.failures:
        sys.exit(2)
    sys.exit(1 if args.check and rep.changes else 0)


if __name__ == "__main__":
    main()
