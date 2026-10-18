# Updating the MCU

Last updated: 2026-10-18 (PyMCU 4.0.0)

Updates come as one file named like `PyMCU_4.0.0.mcu`. Installing it takes about a minute. If anything goes wrong, the MCU keeps the version it had and your data is never touched.

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
    Install PyMCU 4.0.0 from PyMCU_4.0.0.mcu?
    Installed now: 3.5.2. The MCU restarts when the update is done.
    ```

    Tap **Yes** to install, or **No** to leave everything as it is.
5. **Wait.** The status bar shows "Updating to 4.0.0... do not remove USB or power." Leave the stick in and the power on.
6. **The MCU restarts by itself.** The status bar shows "Update to 4.0.0 installed. Restarting... remove USB."
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
- **Using the MCU** from finding the DFMs to analysing the data is described in [UserGuide.md](UserGuide.md).
- **New in 4.0.0:**
    - **Paradigms.** A program names the rules that light the LEDs (open loop, closed loop, fixed interval, non-feeding, progressive ratio and fixed ratio) in `[Paradigm]` sections, and each Interval line names the one it uses. See [ProgramFormat.md](ProgramFormat.md). Progressive ratio and fixed ratio count feeding bouts, and they and fixed interval can start with a set number of closed-loop Activations (Acclimation).
    - **Old programs still load,** except those using the old progressive ratio or the training count in OptoFrequency. Those are refused with a message that explains how to rewrite them ([ProgramFormat.md](ProgramFormat.md), Converting old programs).
    - **A program with a mistake doesn't load.** The message gives the line number and the problem, and a misspelled setting is an error instead of being ignored.
    - **DFM firmware 4.0.0** is needed for progressive ratio, fixed ratio and Acclimation, and a 4.0.0 board needs PyMCU 4.0.0. Older boards keep running everything else.
    - **The data files have 63 more columns** (90 in all): the Interval, Cycle and Paradigm, and for each Well its Phase, Activations, Requirement, Progress and LED on-time. They are filled for 4.0.0 boards and `NA` for older ones, and the Well signals no longer have 65536 added during training. Analyse them with a pyflic that has PyMCU 4.0 support. See [DataFileColumns.md](DataFileColumns.md).
    - **The DFM page** shows the Paradigm, its type and the Interval and Cycle in place of the frequency, pulse width and opto state. Tick **Well details** for each Well's Paradigm state in place of the plot.
    - `Constant` programs now run their Interval, and `StartTime` also accepts `HH:MM`.
    - **Messages** that repeat are written once with a count, lost records are reported with their index range and time, and error flags are named.
- **New in 3.5.2** (also in 4.0.0):
    - Programs start at the top of a minute, as the start time shows, and **Start now** means the next whole minute.
    - Baselines come from the first 2 s of the recording, not from before the start, and the LEDs get their settings only once the baseline is done, so they stay off for the first few seconds of a run.
    - While a program waits for its start time, only the DFM on screen is read, so its live view stays current.
    - A program file can give one `[DFM]` section `ID: All` for every DFM it doesn't list by number.
    - Two more settings are refused when a program loads, because the DFM would run them as a 1 ms flash or ignore them: progressive ratio with OptoDecay 0, and a training count with any rule but progressive ratio. See [FirmwareCompatibility.md](FirmwareCompatibility.md), which also lists test programs for each opto rule.
- **For support,** the MCU keeps a log of each update at `~/PyMCU/mcu.log`, which we can read remotely.
