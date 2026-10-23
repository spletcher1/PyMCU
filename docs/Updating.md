# Updating the MCU

Last updated: 2026-10-16 (PyMCU 3.5.2)

Updates come as one file named like `PyMCU_3.5.2.mcu`. Installing it takes about a minute. If anything goes wrong, the MCU keeps the version it had and your data is never touched.

## You need

- The `.mcu` update file you were sent
- A USB stick
- An MCU that is **not running an experiment**. The Update MCU button is locked while a program runs.
- For some updates, an internet connection on the MCU. You'll be told if your update needs one.

## Steps

1. **Copy the update file onto the USB stick.**
    - Copy the `.mcu` file as it is. Don't open, unzip or rename it.
    - It can go at the top level of the stick or in a folder named `FLICUpdates`.
    - Put only **one** update file on the stick. Delete older `.mcu` files first.
    - The stick can also hold your `FLICData` and `FLICPrograms` folders.
2. **Plug the stick into the MCU.** The status bar shows "USB connected...".
3. **Open the update.** Tap **About** on the toolbar, then **Settings**, then **Update MCU**.
4. **Check the version and confirm.** The prompt names the file and shows the new version next to the installed one, for example:

    ```
    Install PyMCU 3.5.2 from PyMCU_3.5.2.mcu?
    Installed now: 3.5.1. The MCU restarts when the update is done.
    ```

    Tap **Yes** to install, or **No** to leave everything as it is.
5. **Wait.** The status bar shows "Updating to 3.5.2... do not remove USB or power." Leave the stick in and the power on.
6. **The MCU restarts by itself.** The status bar shows "Update to 3.5.2 installed. Restarting... remove USB."
7. **Check.** After the restart, remove the stick and tap **About**. It should show the new version.

## Messages

| Message | Meaning | What to do |
| --- | --- | --- |
| The Update MCU button is greyed out | No USB stick detected, or a program is running or data is copying | Plug in the stick and wait a second; stop the experiment first |
| No update file (.mcu) found on the USB. | The file isn't on the stick, or the browser changed it | Copy the `.mcu` file again; check the name ends in `.mcu` |
| More than one update file on the USB (…); leave only one. | Several `.mcu`/`.tgz` files on the stick | Delete all but the new one |
| Update not started: Not a readable update package … | The file is damaged, often from an incomplete download | Download and copy it again |
| Update failed: Installing new Python packages failed (is the MCU online?) … The previous version was kept. | This update needs internet | Connect the MCU to a network and try again, or contact us |
| Update failed: The updated code does not load … The previous version was kept. | The update has a problem | Nothing changed. Send us the message |
| Update installed. Restart the MCU to use it. | Installed, but the MCU couldn't restart itself | Use **Power Off**, then power it on again. Tell us, since this unit needs a settings fix |

In every "Update failed" or "Update not started" case, nothing on the MCU changed and it keeps working as before.

## Good to know

- **Your data and programs are safe.** Updates never change recorded data (`FLICData`), saved programs (`FLICPrograms`) or the light/dark theme setting.
- **Going back** to an older version works the same way, with the older `.mcu` file.
- **Which programs your DFMs can run** depends on their firmware. From 3.5.1 the MCU checks each program against the connected boards and names anything a board would misread; see [FirmwareCompatibility.md](FirmwareCompatibility.md).
- **New in 3.5.2:**
    - Programs start at the top of a minute, as the start time shows, and **Start now** means the next whole minute.
    - Baselines come from the first 2 s of the recording, not from before the start, and the LEDs get their settings only once the baseline is done, so they stay off for the first few seconds of a run.
    - While a program waits for its start time, only the DFM on screen is read, so its live view stays current.
    - A program file can give one `[DFM]` section `ID: All` for every DFM it doesn't list by number.
    - Two more settings are refused when a program loads, because the DFM would run them as a 1 ms flash or ignore them: progressive ratio with OptoDecay 0, and a training count with any rule but progressive ratio. See [FirmwareCompatibility.md](FirmwareCompatibility.md), which also lists test programs for each opto rule.
- **For support,** the MCU keeps a log of each update at `~/PyMCU/mcu.log`, which we can read remotely.
