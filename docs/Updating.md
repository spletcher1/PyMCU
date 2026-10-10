# Updating an MCU from a USB stick

Last updated: 2026-10-09 (PyMCU 3.5.0)

An update is a single file, `PyMCU_<version>.mcu`. You build it from the repo and send it to the user. The user copies it onto a USB stick and presses **Update MCU**. The MCU checks the file, installs it, confirms the new code loads, and restarts. If anything fails, it keeps the version it had.

## 1. Build the update (maintainer)

1. Raise the version in **both** places, using the same number:
    - `APP_VERSION` in `MainViewModel.py` (shown in the About box and in the update prompt)
    - `version` in `pyproject.toml`
2. Commit the changes. The package is built from the last commit, so uncommitted edits are left out and every package matches a commit.
3. Run `./CreateVersion.sh` in the repo. It prints, for example:

    ```
    Created PyMCU_3.5.1.mcu (version 3.5.1, commit 1a2b3c4).
    ```

    It warns if there are uncommitted changes.
4. Optionally tag the commit (`git tag v3.5.1 && git push --tags`) so you can rebuild the same package later.
5. Test it on a bench MCU before sending it out (section 4).

The package contains the app's code, `images/`, `RunMCU.sh`, `pyproject.toml` and `uv.lock`. It never contains, and so never touches, the MCU's recorded data (`FLICData`), its programs (`FLICPrograms`), its light/dark theme setting (`theme.txt`), its log or its Python environment (`.venv`).

The `.mcu` file is an ordinary `.tar.gz` with a different extension. The extension stops browsers (notably Safari on a Mac) from unpacking it on download. The MCU still accepts `.tgz` files built by older versions of `CreateVersion.sh`.

## 2. Instructions to send with the file

> 1. Copy the attached file `PyMCU_3.5.1.mcu` onto a USB stick. Don't open, unzip or rename it. Put only this one update file on the stick.
> 2. Make sure no experiment is running on the MCU.
> 3. Plug the stick into the MCU.
> 4. Tap **About** on the toolbar, then **Settings**, then **Update MCU**.
> 5. Check the version in the prompt and tap **Yes**. Leave the stick in and the power on until the MCU restarts (about a minute).
> 6. After the restart, remove the stick. **About** should show the new version.
>
> If the MCU shows "Update failed", nothing was changed. Send us the message it shows.

The file can be at the top level of the stick or in a folder named `FLICUpdates`. A stick that also holds `FLICData` or `FLICPrograms` works too.

## 3. What the MCU does when Update MCU is pressed

| Step | What happens | If it fails |
| --- | --- | --- |
| Find the file | Looks for one `.mcu` (or `.tgz`) at the top of each USB drive and in its `FLICUpdates` folder. Hidden files, such as the `._` copies a Mac writes, are ignored. | "No update file (.mcu) found on the USB." or "More than one update file …; leave only one." |
| Check the file | Reads the whole archive and rejects it if it's damaged, holds unsafe paths (absolute or `..`) or links, or has no `MainViewModel.py`. | "Update not started: …". Nothing changed. |
| Confirm | Shows the package's version next to the installed one. | Cancel leaves everything as it was. |
| Back up | Saves every file the update will replace. | |
| Unpack | Unpacks over the app folder. Buttons stay locked until it finishes. | Files restored. |
| New packages | If `uv.lock` changed, runs `uv sync --frozen` to install the new Python packages. **Needs an internet connection.** | Files and packages restored. "… is the MCU online?" |
| Load check | Imports the updated `MainViewModel.py` in a separate process, which catches typing errors and missing packages. | Files restored, with the error shown. |
| Restart | Flushes the disk and reboots (`sudo shutdown -r now`). | "Update installed. Restart the MCU to use it." The sudoers step in [Pi5Setup.md](Pi5Setup.md) section 7 is missing. |

The Update MCU button only works with a USB drive present. It is locked while a program runs or data is copying, so an update can't restart the MCU mid-experiment.

Every step is written to `~/PyMCU/mcu.log` (look for lines starting with `Installing update` and `Update:`).

## 4. Before sending an update

- [ ] Version raised in `MainViewModel.py` and `pyproject.toml`, and committed
- [ ] `./CreateVersion.sh` gave no uncommitted-changes warning
- [ ] Installed on a bench MCU with **Update MCU**; About shows the new version after the restart
- [ ] If `pyproject.toml` or `uv.lock` changed: the user's MCU has internet during the update, or you update it yourself over SSH (`git pull && uv sync`)

## 5. Limits

- **Only for MCUs already on 3.5.0 or later.** This process needs the uv setup from [Pi5Setup.md](Pi5Setup.md). Older MCUs (a pip virtual environment under `/home/pi`, older update code) must not get a 3.5 package: their old updater would unpack it without checks, and the new `RunMCU.sh` would then fail to start. Set those up fresh from Pi5Setup.md.
- **New Python packages need internet.** Without it, the update rolls back cleanly and the MCU keeps working on the old version.
- **No undo button.** To go back a version, send the older `.mcu` file. Rebuild it from its tag if needed.
- **Files are not deleted.** A file removed from the repo stays on the MCU after an update. That's harmless unless the code looks for it.
- **Not signed.** Anyone who can build a package and get it onto a stick can install it, the same as anyone with the source. Physical access to the MCU is the control.
