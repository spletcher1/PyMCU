"""Installs a USB update package (PyMCU_<version>.mcu, a .tar.gz built by CreateVersion.sh) over the running app.

The install is checked and can be undone: the archive is validated first, the files it will
replace are backed up, new Python packages are installed if uv.lock changed, and the updated
code must import cleanly. If any step fails, the previous files are put back.
"""
import os
import re
import subprocess
import tarfile
import tempfile

UV = os.path.expanduser("~/.local/bin/uv")


def ReadArchiveVersion(path):
    """APP_VERSION of the MainViewModel.py inside the package, or None."""
    try:
        with tarfile.open(path) as archive:
            source = archive.extractfile("./MainViewModel.py").read().decode("utf-8", "replace")
    except (OSError, KeyError, tarfile.TarError):
        return None
    match = re.search(r'^APP_VERSION = "([^"]+)"', source, re.MULTILINE)
    return match.group(1) if match else None


def CheckArchive(path):
    """Error message if the file isn't a usable update package, else None."""
    try:
        with tarfile.open(path) as archive:
            members = archive.getmembers()
    except (OSError, tarfile.TarError) as e:
        return "Not a readable update package: " + str(e)
    for m in members:
        name = os.path.normpath(m.name)
        if os.path.isabs(m.name) or name == ".." or name.startswith("../"):
            return "Unsafe path in package: " + m.name
        if not (m.isfile() or m.isdir()):
            return "Unsupported entry in package: " + m.name
    if "./MainViewModel.py" not in [m.name for m in members]:
        return "Package does not contain MainViewModel.py"
    return None


def _Run(command, appDirectory, timeout):
    """Error message (the command's last output lines) or None."""
    try:
        result = subprocess.run(command, cwd=appDirectory, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return str(e)
    if result.returncode != 0:
        output = (result.stderr or result.stdout).strip().splitlines()
        return " / ".join(output[-3:]) or "exit code " + str(result.returncode)
    return None


def _ReadFile(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def InstallUpdate(path, appDirectory):
    """Installs the package into appDirectory. Returns (success, message)."""
    error = CheckArchive(path)
    if error:
        return False, error

    with tarfile.open(path) as archive:
        files = [m.name for m in archive.getmembers() if m.isfile()]
    existing = [f for f in files if os.path.isfile(os.path.join(appDirectory, f))]
    added = [f for f in files if f not in existing]
    lockBefore = _ReadFile(os.path.join(appDirectory, "uv.lock"))

    # Back up every file the update will replace, so a failed update can be undone.
    backup = tempfile.NamedTemporaryFile(prefix="pymcu_backup_", suffix=".tgz", delete=False)
    backup.close()
    try:
        with tarfile.open(backup.name, "w:gz") as archive:
            for f in existing:
                archive.add(os.path.join(appDirectory, f), arcname=f)

        def Restore(reason):
            for f in added:
                try:
                    os.remove(os.path.join(appDirectory, f))
                except OSError:
                    pass
            with tarfile.open(backup.name) as archive:
                archive.extractall(appDirectory, filter="data")
            if lockChanged:
                _Run([UV, "sync", "--frozen"], appDirectory, 600)
            return False, reason + " The previous version was kept."

        lockChanged = False
        try:
            with tarfile.open(path) as archive:
                archive.extractall(appDirectory, filter="data")
        except (OSError, tarfile.TarError) as e:
            return Restore("Unpacking failed: " + str(e) + ".")

        lockChanged = _ReadFile(os.path.join(appDirectory, "uv.lock")) != lockBefore
        if lockChanged:
            # New or changed Python packages: needs an internet connection.
            error = _Run([UV, "sync", "--frozen"], appDirectory, 600)
            if error:
                return Restore("Installing new Python packages failed (is the MCU online?): " + error + ".")

        # The updated code must at least load, or the MCU would not start after the restart.
        error = _Run([UV, "run", "--no-sync", "python", "-c", "import MainViewModel"], appDirectory, 180)
        if error:
            return Restore("The updated code does not load: " + error + ".")
    finally:
        os.remove(backup.name)

    return True, "Update installed."
