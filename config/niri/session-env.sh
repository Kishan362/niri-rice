#!/usr/bin/env bash
set -euo pipefail

command -v dbus-update-activation-environment >/dev/null 2>&1 || exit 0

if [ -d /run/systemd/system ]; then
    dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP
else
    dbus-update-activation-environment WAYLAND_DISPLAY XDG_CURRENT_DESKTOP
fi
