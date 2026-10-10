#!/bin/sh
# Started at login from ~/.config/labwc/autostart.
cd "$(dirname "$(readlink -f "$0")")"
export QT_QPA_PLATFORM=wayland
exec "$HOME/.local/bin/uv" run --no-sync python MainViewModel.py
