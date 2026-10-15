# PyMCU Setup on Raspberry Pi 4 and 5 (Trixie / labwc)

Last updated: 2026-10-14

## Overview

This guide (it replaces the old NotesForPI5 and the Pi 4 Notes.txt) is for a Raspberry Pi 4 or Pi 5 running Raspberry Pi OS Trixie (64-bit), the 3.x branch and PyQt6. It covers install, start on boot, screen blanking, USB drives and a near-kiosk desktop.

One branch and one setup serve both models. The code tells them apart at run time (the About box shows P4 or P5 and which clock it found). What differs is a few lines in `config.txt` (section 1) and the real-time clock (section 7); everything else on this page applies to both.

**Quick route.** Once the OS is flashed, the user created and the repo cloned (the start of sections 1 and 2), one script applies the rest of this guide:

```sh
sudo scripts/mcu-config.py PI5            # Pi 5, original 800x480 display
sudo scripts/mcu-config.py PI5 Rotated    # Pi 5, Touch Display 2 (add --left if the display is turned the other way)
sudo scripts/mcu-config.py PI4            # Pi 4, original display, DS3231 clock module
```

It checks every setting from `config.txt` to the boot splash, fixes what is wrong, adds what is missing, reports each item, and says whether a reboot is needed; `--check` only reports. It does not flash the OS, set auto-login, the timezone or the hostname, install uv or gh, or touch SSH and passwords: those steps stay by hand. The rest of this page explains what the script sets and is the reference for doing any of it by hand.

What changed from the Bookworm notes:

- **Desktop:** Trixie uses the labwc Wayland compositor, not Wayfire. `~/.config/wayfire.ini` is no longer read; autostart and idle settings live in `~/.config/labwc/autostart`.
- **Python:** a uv environment inside the repo replaces the venv, `--system-site-packages`, PyQt5 and `get-pip.py`.
- **User:** the setup runs as the logged-in user (here `flic`) with no `/home/pi` or `/media/pi` symlinks. The app finds its own folder and the user's USB mount point.
- **X11:** the lightdm and lxsession steps are no longer needed. Wayland is the only target.

## 1. OS and hardware interfaces

Flash Raspberry Pi OS (64-bit, desktop) with Raspberry Pi Imager, create the user, and enable desktop auto-login. The 64-bit image is required on both models: PyQt6 has no 32-bit wheels. Then in `sudo raspi-config`, Interface Options:

- **I2C:** on (DFMs and the environmental sensors on bus 1).
- **Serial port:** hardware on, login shell off. The DFM link is `/dev/ttyAMA0` (the PL011 UART on GPIO 14/15), set in `COMM.py`. The login shell must be off, or a console would share the DFM port.
- **SPI and Remote GPIO:** not used by the app; leave off.

### config.txt by model

`/boot/firmware/config.txt` is the one place the two models differ. Put the lines for your model under `[all]`, then reboot. raspi-config writes `dtparam=i2c_arm=on` (I2C) and `enable_uart=1` (serial port) itself; add the rest by hand.

| Purpose | Pi 5 | Pi 4 |
| --- | --- | --- |
| I2C bus for DFMs and sensors | `dtparam=i2c_arm=on` | `dtparam=i2c_arm=on` |
| DFM link on `/dev/ttyAMA0` | `dtparam=uart0=on` | `enable_uart=1` and `dtoverlay=disable-bt` |
| Real-time clock | built in; `dtparam=rtc_bbat_vchg=3000000` charges its battery (section 7) | `dtoverlay=i2c-rtc,ds3231` for the DS3231 module |

Why the Pi 4 lines differ:

- **UART.** On a Pi 4 the PL011 UART (`ttyAMA0`) is wired to the Bluetooth chip, and GPIO 14/15 get the mini UART (`ttyS0`), whose baud rate follows the core clock and is not reliable at the DFM link's 250000 baud. `dtoverlay=disable-bt` turns Bluetooth off and puts `ttyAMA0` back on GPIO 14/15. Also run `sudo systemctl disable hciuart`, so nothing tries to bring Bluetooth up on that port. (To keep Bluetooth, use `dtoverlay=miniuart-bt` with `core_freq=250` instead; the MCU has no use for it.) On the Pi 5 `ttyAMA0` is free, and `dtparam=uart0=on` enables it.
- **Serial console.** With `disable-bt`, `serial0` is `ttyAMA0`, so `console=serial0,115200` in `cmdline.txt` would put a login console on the DFM port. "Login shell off" in raspi-config removes it; check that `/boot/firmware/cmdline.txt` has no `console=serial0`. On the Pi 5 `console=serial0` points at the separate debug UART (`ttyAMA10`) and does no harm.
- **Clock.** The Pi 5 has a built-in RTC. The Pi 4 has none, so it keeps the DS3231 module (I2C address `0x68`) that the older MCUs were built with. `dtoverlay=i2c-rtc,ds3231` makes it `/dev/rtc0`; the kernel sets the system time from it when the driver loads at boot, and the app's Set Date and Time writes to it. The `hwclock-set` edit from the old Pi 4 notes should not be needed on Trixie: if the time is wrong after the power-off test in section 8, check `dmesg | grep rtc`.

After the reboot, `ls -l /dev/ttyAMA0 /dev/rtc0` must list both. The About box shows which clock the app found: the battery reading on a Pi 5, "Clock: DS3231 module" on a Pi 4, or "Clock: no RTC found" when the overlay is missing.

The user must be in the `gpio`, `i2c` and `dialout` groups (default for the first user). Check with `id`.

The hostname must contain `MCU`. The app uses real hardware only when it does, and puts the hostname in data folder names. Recommended: `FLICMCU` (see Optional steps).

Set the timezone in raspi-config, Localisation Options.

## 2. Install the app

The app lives in `~/PyMCU` and runs from a uv environment defined by `pyproject.toml` (Python 3.13). No sudo or system Python packages are needed.

1. Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh` (installs to `~/.local/bin/uv`).
2. Log in to GitHub (the repo is private): `sudo apt install gh`, then `gh auth login` (GitHub.com, HTTPS, log in with a web browser) and `gh auth setup-git`. This also lets `git pull` and `git push` work later.
3. Clone the branch for this version: `git clone -b v4_Dev https://github.com/spletcher1/PyMCU.git ~/PyMCU` (it serves Pi 4 and Pi 5 alike)
4. Build the environment: `cd ~/PyMCU && uv sync`

GPIO uses `adafruit-lgpio`, a prebuilt wheel of lgpio 0.2.2, which gpiozero uses on both models. The plain `lgpio` package compiles from source and would need `sudo apt install swig liblgpio-dev` first.

## 3. Start on boot

labwc runs `~/.config/labwc/autostart` at login, which launches `RunMCU.sh`. The script is in the repo:

```sh
#!/bin/sh
# Started at login from ~/.config/labwc/autostart.
cd "$(dirname "$(readlink -f "$0")")"
export QT_QPA_PLATFORM=wayland
# Keep app output in mcu.log (previous run's log rotated to mcu.log.1 once it passes 5 MB).
if [ -f mcu.log ] && [ "$(stat -c %s mcu.log)" -gt 5000000 ]; then mv mcu.log mcu.log.1; fi
exec "$HOME/.local/bin/uv" run --no-sync python -u MainViewModel.py >>mcu.log 2>&1
```

It changes into its own folder because the app reads `Mainwindow.ui` and `theme.txt`, and writes `FLICData/`, relative to the working directory. `--no-sync` stops uv from touching the network at boot.

**Log file.** Everything the app prints goes to `~/PyMCU/mcu.log`: the version at each start, failed copies, unmounts, clock and power-off errors, and the full traceback of any unexpected error. The app logs such errors and keeps running instead of closing. Check this file first when a user reports a problem.

Add this line to the end of `~/.config/labwc/autostart`:

```
/home/flic/PyMCU/RunMCU.sh &
```

Replace `flic` with the actual user name.

## 4. Screen blanking

The screen turns off after 60 seconds idle and wakes on touch. Turn on screen blanking in raspi-config (Display Options), which adds a `swayidle` line to `~/.config/labwc/autostart`. Then change its timeout from 600 to 60:

```
swayidle -w timeout 60 'wlopm --off \*' resume 'wlopm --on \*' &
```

After setup, change the time from the app: About → Settings → **Screen off after**, with − and + stepping through Never, 15 s to 3600 s. The app rewrites this `swayidle` line, so the time survives a reboot, and restarts `swayidle` so it applies at once. Never removes the line.

This replaces the `[idle]` section of the old `wayfire.ini`. Keep `myapp.showFullScreen()`: the 10/5/25 note says recent PyQt no longer blocks blanking in full screen.

## 5. USB drives and updates

USB drives mount automatically at `/media/<user>/<label>`, with no pop-up. The app copies data there and unmounts the drive when a copy succeeds.

Create `~/.config/pcmanfm/default/pcmanfm.conf` from `/etc/xdg/pcmanfm/default/pcmanfm.conf` and set, under `[volume]`:

```
mount_on_startup=1
mount_removable=1
autorun=0
```

`autorun=0` replaces unticking "Show available options for mountable media". The system default ships with `mount_removable=0`.

The app needs no `/home/pi` or `/media/pi` symlinks:

- `GetUSBDrives()` checks `/media/<user>`, plus `/media/pi` if it exists.
- Updates are a single `PyMCU_<version>.mcu` file on a USB stick, installed with **Update MCU**. Building them: [Packaging.md](Packaging.md). Installing them: [Updating.md](Updating.md).
- Unmounting uses plain `umount`, which works for desktop mounts through udisks2's `umount.udisks2` helper.

**How the app handles USB (3.5.0).**

- **Detection:** once a second the app checks which drives are actually mounted. Plugging other USB devices (keyboard, hub) in or out no longer changes the buttons. A folder left behind by a stick pulled without unmounting is ignored.
- **Locking:** Save data, Move programs and Update are enabled only with a drive present, and stay locked while a program runs or a copy is in progress.
- **Save data:** cancelling leaves the stick mounted. After a successful copy the app flushes the data and unmounts, and says so only if the unmount worked. A failed copy shows the reason (for example "No space left on device") and leaves the stick mounted for a retry. Files are copied without permission bits, so FAT-formatted sticks work.
- **Programs:** `.txt` files are found in any letter case (`PROGRAM.TXT`). Files saved on Windows with characters such as `°` or `µ` preview instead of crashing the app.

**Which drive is used.** Save data and Move programs use the first drive, in name order, that has their folder at the top level. Drives without that folder are ignored, so an unrelated second stick does no harm.

| Action | Folder required on the stick |
| --- | --- |
| Save data | `FLICData` |
| Move programs | `FLICPrograms` (`.txt` files) |
| Update | none: one `.mcu` file at the top of the stick or in `FLICUpdates` |

Prepare each stick with the folders it will be used for. A blank stick is rejected with "No USB with a FLICData folder found."

## 6. Kiosk appearance

The app fills the screen. Behind it the desktop is plain black, with no icons and a trimmed taskbar.

**Black desktop, no icons.** Copy `desktop-items-0.conf` and `desktop-items-1.conf` from `/etc/xdg/pcmanfm/default/` into `~/.config/pcmanfm/default/` and set:

```
wallpaper_mode=color
desktop_bg=#000000000000
show_documents=0
show_trash=0
show_mounts=0
```

**Taskbar.** `~/.config/wf-panel-pi/wf-panel-pi.ini`:

```
[panel]
widgets_left=spacing4
widgets_right=tray power spacing2 connect spacing2 bluetooth spacing2 netman spacing2 volumepulse spacing2 clock spacing2 batt spacing2 squeek
notify=false
```

This removes the menu button, launchers, window list, ejecter and updater. The on-screen keyboard button (`squeek`) stays for touch input.

**Keyboard shortcuts.** A USB keyboard could otherwise open a terminal (Ctrl+Alt+T) or the app menu (Super) over the app. Unbind those and the shortcuts that close or switch away from the app in `~/.config/labwc/rc.xml`. labwc merges this file with the system defaults; keep any `<touch>` line already there.

```xml
<keyboard>
  <keybind key="C-A-t"><action name="None" /></keybind>
  <keybind key="W-Return"><action name="None" /></keybind>
  <keybind key="Super_L" onRelease="yes"><action name="None" /></keybind>
  <keybind key="A-F2"><action name="None" /></keybind>
  <keybind key="A-F3"><action name="None" /></keybind>
  <keybind key="A-F4"><action name="None" /></keybind>
  <keybind key="A-Tab"><action name="None" /></keybind>
  <keybind key="A-space"><action name="None" /></keybind>
</keyboard>
```

Apply with `kill -HUP $(pgrep -x labwc)` or a reboot. Volume, screenshot, lock (Ctrl+Alt+L) and the shutdown dialog (Ctrl+Alt+Del) still work. With no menu or terminal on the device, maintenance is over SSH (for example Cursor's remote connection). To restore the shortcuts, delete the `<keyboard>` block.

**Cursor.** When the hostname contains `MCU`, `main()` in `MainViewModel.py` sets a blank cursor, so no pointer shows even before the first touch. A plugged-in mouse also shows no pointer over the app.

**Screen size.** The window is laid out for the 800x480 touch display and fixed at that size in `Mainwindow.ui`. When the hostname contains `MCU` and the screen is bigger, `main()` starts the app again with Qt's `QT_SCALE_FACTOR` set to the largest quarter step at which the layout fits, which scales widgets, fonts, style sheets, dialogs and the plot together. On the 1280x720 Touch Display 2 that is 1.5, so the app shows as 1200x720 with a 40 px margin at each side. A factor already in the environment is kept, so `export QT_SCALE_FACTOR=1` in `RunMCU.sh` turns scaling off, and `QT_SCALE_FACTOR=1.5` previews the Touch Display 2 layout on any machine.

**Touch Display 2 orientation.** The Touch Display 2 is a portrait panel (720x1280). For landscape, set Orientation to Right (or Left, depending on which way the display is mounted) in the desktop's Screen Configuration tool, which keeps the setting for later logins. The Wayland compositor applies this rotation, so it is not in effect during boot: see the rotated splash note in section 7.

**Dialogs.** Message boxes already set the main window as parent and use `WindowStaysOnTopHint`, so they stay in front under Wayland.

## 7. System settings (need sudo)

### Required: power-off, clock and update reboot

The app powers off the Pi, sets the clock and reboots after an update with `sudo -n`, which never prompts for a password. New Raspberry Pi OS users need a password for sudo, so allow exactly these commands. Without this, those buttons report an error and do nothing.

```sh
sudo apt install util-linux-extra      # provides hwclock
echo 'flic ALL=(root) NOPASSWD: /usr/sbin/shutdown, /usr/bin/date, /usr/sbin/hwclock' | sudo tee /etc/sudoers.d/pymcu
sudo chmod 440 /etc/sudoers.d/pymcu
sudo visudo -cf /etc/sudoers.d/pymcu   # must print "parsed OK"
```

Replace `flic` with the actual user name. Check with `sudo -n /usr/sbin/hwclock -r`, which should print the RTC time without asking for a password.

### Required: real-time clock

Setting the time in the app runs `date` and then `hwclock -w`, which writes it to `/dev/rtc0`. Which clock that is depends on the model.

**Pi 5: built-in RTC.** The RTC keeps time through power loss only with a battery on the J5 (BAT) connector.

Use a rechargeable lithium-manganese cell, such as the official Raspberry Pi RTC battery (ML-2020). **Charging is off by default** (`/sys/class/rtc/rtc0/charging_voltage` reads `0`). Turn it on by adding this under `[all]` in `/boot/firmware/config.txt`, then reboot:

```
dtparam=rtc_bbat_vchg=3000000
```

Check with `cat /sys/class/rtc/rtc0/charging_voltage` (should print `3000000`) and `cat /sys/class/rtc/rtc0/battery_voltage` (non-zero with the battery connected). The About box shows the same reading, for example "Clock battery: 2.95 V, OK" and "Battery charging: on": OK at 2.5 V and above, low below that, "none connected" under 0.5 V. A new ML-2020 usually arrives partly discharged and reads low until it has charged for a day or so with the Pi powered. Never enable charging with a CR2032 or other non-rechargeable coin cell: it can leak or swell.

Leave `dtoverlay=i2c-rtc,ds3231` out of a Pi 5's `config.txt`, so a DS3231 module left over from an older MCU can't compete with the built-in RTC for `/dev/rtc0`. The module can be removed from Pi 5 units.

**Pi 4: DS3231 module.** The Pi 4 has no built-in RTC, so it keeps the DS3231 module at I2C address `0x68`, enabled with `dtoverlay=i2c-rtc,ds3231` (section 1). The module runs on its own coin cell, which the kernel cannot read, so the About box shows "Clock: DS3231 module" and "Clock battery: not monitored". If the time is wrong after a power-off, replace the cell. Nothing else is needed: no `rtc_bbat_vchg`, and no charging settings.

### Optional

- **SSH key-only login:** keep SSH on, since remote maintenance depends on it. From your computer run `ssh-copy-id flic@<pi>` and confirm you (and Cursor) connect without a password. Only then add `PasswordAuthentication no` to `/etc/ssh/sshd_config.d/kiosk.conf` and run `sudo systemctl restart ssh`. Doing it in the other order locks you out.
- **Password:** give the user a strong password. sudo asks for it, so it is what stops a user who gets past the app from changing the system.
- **Hostname:** `sudo raspi-config nonint do_hostname FLICMCU`, then reboot.
- **Quieter boot:** add `logo.nologo vt.global_cursor_default=0 loglevel=3` to the single line in `/boot/firmware/cmdline.txt`. `quiet splash` is already there. This hides the Pi logos, the console cursor and most kernel messages at boot and shutdown.

### Custom boot splash

The "Welcome to the Raspberry Pi Desktop" screen is the Plymouth theme `pix`, which centers `splash.png` on black. Copy it to a theme of your own rather than editing `pix`, which OS updates overwrite. This uses the FLIC logo from the repo (`images/MCU.png`, 800×480):

```sh
T=/usr/share/plymouth/themes
sudo cp -r $T/pix $T/flic
cd $T/flic
sudo mv pix.plymouth flic.plymouth
sudo mv pix.script flic.script
sudo sed -i 's/^Name=pix/Name=flic/; s/^Description=.*/Description=FLIC MCU splash/; s#themes/pix#themes/flic#g; s/pix\.script/flic.script/' flic.plymouth
sudo cp ~/PyMCU/images/MCU.png splash.png
sudo plymouth-set-default-theme -R flic
sudo reboot
```

`-R` rebuilds the initramfs, which takes about a minute. `plymouth-set-default-theme` with no argument should then print `flic`.

- **Image:** any PNG works. It is centered and only shrunk if larger than the screen. `MCU.png` has a white background, so use a black or transparent version to blend in.
- **Shutdown:** the theme shows no image at shutdown, only black.
- **Requires:** `quiet splash` in `cmdline.txt` (already there). The Pi 5 firmware screen before it is not affected.
- **Undo:** `sudo plymouth-set-default-theme -R pix`

**Touch Display 2: rotated splash.** The splash is drawn before Wayland starts, in the panel's native portrait orientation, so on a Touch Display 2 `MCU.png` appears on its side. Use a pre-rotated copy as `splash.png` instead. The repo has one for each orientation, both 480x800: `images/MCU_Rotated.png` is turned 90° clockwise, for Orientation **Right**; `images/MCU_Rotated_Left.png` is turned counter-clockwise, for **Left**. After the theme is installed as above:

```sh
sudo cp ~/PyMCU/images/MCU_Rotated.png /usr/share/plymouth/themes/flic/splash.png
sudo plymouth-set-default-theme -R flic
```

If the logo then shows upside down, the desktop was rotated the other way: use the other file. The original 800x480 display is landscape by nature and keeps `MCU.png`.

## 8. Verify after reboot

Confirmed on 9 Oct 2026 on a Pi 5: all Python imports load, and `RunMCU.sh` starts the app on the Wayland display with no errors. The Pi 4 steps (section 1 overlays, DS3231) have not yet been run through on a Pi 4 with Trixie. Check the rest after a reboot:

- [ ] `sudo scripts/mcu-config.py <profile> --check` reports nothing to change
- [ ] `/dev/ttyAMA0` and `/dev/rtc0` both exist (Pi 4: needs the `disable-bt` and `i2c-rtc` overlays)
- [ ] About box shows the right model (P4 or P5) and the clock, not "no RTC found"
- [ ] App opens full screen at login, with no pointer
- [ ] Screen blanks after 60 s idle and wakes on touch, with the app in front
- [ ] A USB stick mounts under `/media/<user>/` with no pop-up
- [ ] Copy data to USB, then remove it once the app reports it unmounted
- [ ] Desktop behind the app is black with no icons; taskbar shows no ejecter, updater or notifications
- [ ] With a USB keyboard, Ctrl+Alt+T, Super, Alt+F4 and Alt+Tab do nothing over the app
- [ ] Power off from the app works (sudoers step done)
- [ ] Set the time in the app, power off, unplug for a while: the time is still right (Pi 5: RTC battery charging; Pi 4: DS3231 cell)
- [ ] Unplugging a keyboard or mouse leaves the USB buttons unchanged
- [ ] Boot shows the FLIC splash, if the custom splash was installed
- [ ] A DFM on the serial port and the environmental sensors are detected

Open items:

- `notify=false` was set from the panel's config keys. If notifications still appear, turn them off in the taskbar's Preferences.
- Automount was turned on in the config but not yet tested with a real stick.
