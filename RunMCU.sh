#!/bin/sh
# Started at login from ~/.config/labwc/autostart.
cd "$(dirname "$(readlink -f "$0")")"
export QT_QPA_PLATFORM=wayland
# Keep app output in mcu.log (previous run's log rotated to mcu.log.1 once it passes 5 MB).
if [ -f mcu.log ] && [ "$(stat -c %s mcu.log)" -gt 5000000 ]; then mv mcu.log mcu.log.1; fi
exec "$HOME/.local/bin/uv" run --no-sync python -u MainViewModel.py >>mcu.log 2>&1
