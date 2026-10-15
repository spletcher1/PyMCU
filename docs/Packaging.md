# Packaging and distributing an MCU update

Last updated: 2026-10-09 (PyMCU 3.5.0)

For the developer. An update is one file, `PyMCU_<version>.mcu`, built from a commit on `v4_Dev` and sent to users, who install it from a USB stick with **Update MCU**. The steps for the user are in [Updating.md](Updating.md); send that page, or its short version in section 4, with the file.

## 1. Set the version

Use one number in **both** places:

| File | Line | Used for |
| --- | --- | --- |
| `MainViewModel.py` | `APP_VERSION = "3.5.1"` | About box, update prompt, package name, `mcu.log` |
| `pyproject.toml` | `version = "3.5.1"` | uv project metadata |

Bump the last number for fixes (3.5.0 → 3.5.1) and the middle one for new features (3.5 → 3.6). After editing `pyproject.toml`, run `uv lock` so `uv.lock` records the new version.

## 2. Commit and build

```sh
cd ~/PyMCU
git add -A && git commit -m "Version 3.5.1: <what changed>"
./CreateVersion.sh
```

Output:

```
Created PyMCU_3.5.1.mcu (version 3.5.1, commit 1a2b3c4).
Send it to the user: they copy it onto a USB stick and press Update in the MCU settings.
```

- **Built from the last commit**, with `git archive`. Uncommitted edits are left out, so every package matches a commit. The script warns if there are uncommitted changes; commit and rebuild.
- **Contents:** the app's Python files, `Mainwindow.ui`, `images/`, `RunMCU.sh`, `CreateVersion.sh`, `MCUUpdate.py`, `pyproject.toml` and `uv.lock`.
- **Left out on purpose:** `docs/`, `tests/`, `FLICPrograms/` (the user's programs), `theme.txt` (each MCU's light/dark setting), `.vscode/` and `.gitignore`. Untracked files (`FLICData`, `.venv`, `mcu.log`) are never in a git archive.
- **Format:** `.mcu` is a plain `.tar.gz` (`tar -tzf PyMCU_3.5.1.mcu` lists it). The extension stops browsers, notably Safari, from unpacking the download. The MCU also accepts `.tgz`.
- **Git ignores** `PyMCU_*.mcu` files, so built packages are never committed.

Tag the release so the same package can be rebuilt later:

```sh
git tag v3.5.1
git push origin v4_Dev --tags
```

## 3. Test on a bench MCU

Install the package exactly as a user would: copy it to a stick, then About → Settings → Update MCU. Then check:

- [ ] The prompt shows the new version and the installed one
- [ ] The MCU restarts by itself, and About shows the new version
- [ ] `~/PyMCU/mcu.log` has `Update: Update installed.` and a `PyMCU 3.5.1 starting` line
- [ ] The changes work: DFMs detected, a short program runs, data saves to USB
- [ ] Recorded data, programs and the theme are unchanged

### When dependencies change

If `pyproject.toml` or `uv.lock` changed (a package added, removed or upgraded), the MCU runs `uv sync --frozen` during the update, which **needs internet**. Without it, the update rolls back and the MCU keeps the old version. Before sending, either:

- confirm the user's MCU is online when they update, or
- update that MCU yourself over SSH (`cd ~/PyMCU && git pull && uv sync`), or ask the user to connect it to a network first.

Test this case on a bench MCU both online and offline (offline should report "is the MCU online?" and keep the old version).

## 4. Distribute

Send the `.mcu` file (email, shared drive or download link) with these instructions:

> 1. Copy the attached file `PyMCU_3.5.1.mcu` onto a USB stick. Don't open, unzip or rename it. Put only this one update file on the stick.
> 2. Make sure no experiment is running on the MCU.
> 3. Plug the stick into the MCU.
> 4. Tap **About** on the toolbar, then **Settings**, then **Update MCU**.
> 5. Check the version in the prompt and tap **Yes**. Leave the stick in and the power on until the MCU restarts (about a minute).
> 6. After the restart, remove the stick. **About** should show 3.5.1.
>
> If the MCU shows "Update failed", nothing was changed. Send us the message it shows.

Notes:

- **Email:** a few MB, so it attaches normally. If a mail filter strips it, use a shared link.
- **Renaming is fine** as long as it still ends in `.mcu`. A download that comes back as `PyMCU_3.5.1 (1).mcu` also works.
- **Which MCUs:** only units already on 3.5.0 or later (see Limits).
- **Record** which units got which version. About shows each unit's version.

## 5. Roll back

There is no undo button. To go back, send the previous package:

```sh
git checkout v3.5.0 && ./CreateVersion.sh && git checkout v4_Dev
```

The MCU installs an older version the same way as a newer one. The prompt shows both numbers.

## 6. Limits

- **3.5.0 and later only.** Older MCUs (a pip virtual environment under `/home/pi`, update code without checks) must not get a 3.5 package. Their old updater unpacks it blindly, and the new `RunMCU.sh` then fails to start because uv isn't installed. Set those up fresh from [MCUSetup.md](MCUSetup.md).
- **Removed files stay.** An update adds and replaces files but deletes none. A file removed from the repo stays on the MCU; make sure nothing still imports it.
- **Changes outside the app folder** (`config.txt`, sudoers, labwc settings) can't be made by an update. Do them over SSH and note them in MCUSetup.md.
- **Not signed.** Anyone who can build a package and get it onto a stick can install it. Physical access to the MCU is the control.
- **The load check is basic.** It confirms the code imports, not that it works. That's what the bench test is for.

## How the MCU installs a package

For reference when changing the updater (`MCUUpdate.py`, `RunUpdate` in `MainViewModel.py`):

1. Find exactly one `.mcu`/`.tgz` at the top of a USB drive or in its `FLICUpdates/` folder, skipping hidden files (Mac `._` files).
2. Check the archive: it must read completely, contain no absolute paths, `..` or links, and contain `./MainViewModel.py`.
3. Ask for confirmation, showing both versions.
4. Back up every file the package will replace, to a temporary archive.
5. Unpack into the app folder (`tarfile` with the `data` filter).
6. If `uv.lock` changed, run `uv sync --frozen`.
7. Run `python -c "import MainViewModel"` in the app folder.
8. On any failure: delete the files the package added, restore the backup, and re-sync packages if the lock had changed.
9. On success: flush to disk and reboot with `sudo -n /usr/sbin/shutdown -r now`. This needs the sudoers entry from MCUSetup.md section 7.
