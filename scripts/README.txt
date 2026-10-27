PYMCU SCRIPTS
=============

This folder holds two scripts. Run both from the PyMCU folder.

  mcu-config.py          Sets up a Raspberry Pi as an MCU, for its Pi model and
                         touch display.
  simulate_recording.py  Writes a simulated recording, for testing analysis
                         software without flies.

The full MCU setup guide is docs/MCUSetup.md.


mcu-config.py
=============

mcu-config.py checks every system setting PyMCU needs and fixes any that are
wrong or missing. Settings that are already right are left alone, so it is
safe to run again at any time, for example after an update or after moving the
SD card to another MCU.

Usage:

    sudo scripts/mcu-config.py PROFILE [--left] [--check] [--force]

PROFILE names the Pi model and the screen type. The options are described
below.


Choosing a profile
------------------

  Command                                   Pi     Display
  ----------------------------------------  -----  ---------------------------
  sudo scripts/mcu-config.py PI5            Pi 5   Original 7" touch display
  sudo scripts/mcu-config.py PI5 Rotated    Pi 5   Touch Display 2, turned to
                                                   Orientation Right
  sudo scripts/mcu-config.py PI5 Rotated --left
                                            Pi 5   Touch Display 2, turned to
                                                   Orientation Left
  sudo scripts/mcu-config.py PI4            Pi 4   Original 7" touch display
  sudo scripts/mcu-config.py PI4 Rotated    Pi 4   Touch Display 2, turned to
                                                   Orientation Right
  sudo scripts/mcu-config.py PI4 Rotated --left
                                            Pi 4   Touch Display 2, turned to
                                                   Orientation Left

Profile names can be written in any case, and "Rot" is short for "Rotated":
"pi5 rotated", "PI5-Rotated" and "Pi5Rot" all work.

The script reads the Pi's model and stops if it doesn't match the profile, so
a PI4 profile can't be applied to a Pi 5 by mistake (see --force).


Pi models: PI4 and PI5
----------------------

Both models use I2C for the sensors and the serial port (UART) for the DFM
bus. They differ in how the serial port is freed for the DFMs and in the
real-time clock.

  PI5   Raspberry Pi 5. Uses the built-in real-time clock.
        config.txt:  dtparam=i2c_arm=on
                     dtparam=uart0=on
                     dtparam=rtc_bbat_vchg=3000000   (charges the clock's
                                                      battery)
        Comments out any dtoverlay=i2c-rtc line, so a DS3231 module left
        over from an older MCU can't compete with the built-in clock.
        Disables the serial login console (serial-getty@ttyAMA0).

  PI4   Raspberry Pi 4. Has no built-in clock, so it uses the DS3231 clock
        module the older MCUs were built with.
        config.txt:  dtparam=i2c_arm=on
                     enable_uart=1
                     dtoverlay=disable-bt            (frees the serial port
                                                      from Bluetooth)
                     dtoverlay=i2c-rtc,ds3231        (the DS3231 module)
        Comments out any dtparam=rtc_bbat_vchg line (Pi 5 only).
        Removes console=serial0 and console=ttyAMA0 from cmdline.txt and
        disables the hciuart and serial-getty@ttyAMA0 services, so nothing
        else uses the DFM's serial port.

Both models need Raspberry Pi OS Trixie (64-bit). The script warns if the OS
is a different release.


Screen types: original display and Touch Display 2
--------------------------------------------------

  Original 7" touch display (800x480, landscape)
        Use the profile without "Rotated" (PI4 or PI5). The screen keeps its
        normal orientation, and the boot splash is images/MCU.png.

  Touch Display 2 (720x1280, a portrait panel used in landscape)
        Use the "Rotated" profile (PI4 Rotated or PI5 Rotated). The panel is
        turned a quarter turn, and which way depends on how it is mounted:

          no --left   Orientation Right (kanshi transform 90).
                      Boot splash images/MCU_Rotated.png.
          --left      Orientation Left (kanshi transform 270).
                      Boot splash images/MCU_Rotated_Left.png.

        If the screen is upside down after the next login, run the script
        again with the other choice.

        The app scales itself to fit the larger screen (1.5 times, shown as
        1200x720), so nothing else needs setting.

The orientation is written to ~/.config/kanshi/config, the same file the
desktop's Screen Configuration tool writes. It applies at the next login, or
at once with:  kanshictl reload

The boot splash is drawn before the desktop rotates the screen, which is why
the Touch Display 2 needs a pre-rotated splash image.


Options
-------

  --check   Report only, change nothing. Every line that would change is
            shown as "would add", "would fix" and so on. Use it first on an
            MCU you don't know, and after setup to confirm nothing is left.

  --left    Rotated profiles only: the Touch Display 2 is turned the other
            way (Orientation Left). Ignored without "Rotated".

  --force   Run even when the Pi's model doesn't match the profile, or the
            model can't be read. Not needed in normal use.

  -h, --help
            Show the built-in help.


What the script sets up
-----------------------

  - config.txt and cmdline.txt (in /boot/firmware), for the Pi model above.
    Lines are added under [all]; lines in a [pi4] or [pi5] section count only
    for that model. The originals are saved once, next to themselves, as
    config.txt.mcu-config.bak and cmdline.txt.mcu-config.bak.
  - A quieter boot (quiet, splash, no logo or cursor) in cmdline.txt.
  - The i2c-dev kernel module (/etc/modules).
  - Serial console and Bluetooth services, as described above.
  - The user's groups: gpio, i2c, dialout. These apply at the next login.
  - The app's Python environment (uv sync, if .venv doesn't exist yet), and
    that RunMCU.sh is executable.
  - Starting the app at login, and screen blanking when idle
    (~/.config/labwc/autostart). A new MCU starts at 60 seconds. A time
    already chosen in the app is kept.
  - USB drives mounted automatically, a plain black desktop with no icons,
    and a reduced taskbar.
  - Keyboard shortcuts that would open a terminal or menus switched off
    (~/.config/labwc/rc.xml).
  - Screen orientation, as described above.
  - The hwclock tool, and sudo rights for the app to shut down and set the
    date and clock (/etc/sudoers.d/pymcu).
  - The FLIC boot splash (a Plymouth theme named flic). Installing it
    rebuilds the initramfs, which takes about a minute.

It sets up the files of the user who ran sudo. Run without sudo, it asks for
the password itself when it needs it.

Not covered, do these by hand (see docs/MCUSetup.md):

  - Flashing Raspberry Pi OS Trixie (64-bit).
  - Hostname, timezone and desktop auto-login (sudo raspi-config).
    The hostname must contain "MCU", or the app won't use the hardware; the
    script warns if it doesn't. To set it:
        sudo raspi-config nonint do_hostname FLICMCU
  - Installing uv and gh.
  - SSH key-only login, and the user's password.


Typical setup of a new MCU
--------------------------

  1. Flash the OS, set the hostname, timezone and auto-login, install uv,
     and put PyMCU in the home folder, as in docs/MCUSetup.md.
  2. cd ~/PyMCU
  3. Preview the changes:
         sudo scripts/mcu-config.py PI5 --check
  4. Apply them:
         sudo scripts/mcu-config.py PI5
  5. Reboot:
         sudo reboot
  6. Confirm that nothing is left to change:
         sudo scripts/mcu-config.py PI5 --check

Use your own profile in place of PI5 in steps 3, 4 and 6.

Some steps need the network: creating the Python environment and installing
hwclock.


Moving an SD card or changing the display
-----------------------------------------

Run the script again with the new profile, then reboot.

  - Pi 4 to Pi 5, or back: the clock lines that belong only to the other
    model are commented out and marked "disabled by mcu-config", and the
    new model's lines are added.
  - Original display to Touch Display 2, or back: the orientation and the
    boot splash are changed to match.


Reading the output
------------------

Each setting gets one line:

  ok             already right
  added, fixed,  changed by the script (with --check: "would add",
  removed,       "would fix" and so on)
  disabled,
  installed
  WARNING        something to check by hand; the script carries on
  FAILED         something the script couldn't do

A summary follows, and a reminder to reboot when a change needs one
(config.txt, cmdline.txt, groups or the boot splash).

Exit codes:

  0   done, or with --check: nothing would change
  1   with --check: something would change
  2   something failed, the profile is unknown, or the Pi's model doesn't
      match the profile


Testing on another computer
---------------------------

The script can be tried without a Pi. Nothing is run, only shown:

  MCU_CONFIG_PREFIX=DIR   Take every system file under DIR instead of /.
  MCU_CONFIG_HOME=DIR     Use DIR as the user's home folder.
  MCU_CONFIG_USER=NAME    Set up this user instead of the one who ran sudo.

For example:

    MCU_CONFIG_PREFIX=/tmp/fakepi MCU_CONFIG_HOME=/tmp/fakehome \
        python3 scripts/mcu-config.py PI5 Rotated --check --force


simulate_recording.py
=====================

Writes the data files of a simulated two-hour recording, as an MCU would,
for testing analysis software such as pyflic without flies. Two DFMs (IDs 1
and 2) run choice chambers under a progressive-ratio program with DFM
firmware 4.0.0. A _truth folder beside the data lists every simulated
feeding bout and light period, to check an analysis against.

Usage:

    .venv/bin/python scripts/simulate_recording.py [--out DIR] [--seed N]
        [--start "MM/DD/YYYY HH:MM:SS"]

  --out DIR     Where to write the files. Default: ~/SimulatedFLICData
  --seed N      Random seed. The same seed gives the same recording.
                Default: 1
  --start TIME  When the simulated recording starts.
                Default: "10/17/2026 13:00:00"
