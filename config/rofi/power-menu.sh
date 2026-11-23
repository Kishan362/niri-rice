#!/usr/bin/env bash
set -euo pipefail

entries=(
    "Lock|system-lock-screen"
    "Logout|system-log-out"
    "Suspend|system-suspend"
    "Reboot|system-reboot"
    "Shutdown|system-shutdown"
)

choice="$(
    for entry in "${entries[@]}"; do
        printf '%s\000icon\037%s\n' "${entry%%|*}" "${entry##*|}"
    done | rofi -dmenu -i -p "Power" -show-icons -no-custom \
        -theme-str 'window { width: 360px; } listview { lines: 5; }'
)" || exit 0

case "$choice" in
    Lock) swaylock --indicator-idle-visible ;;
    Logout) niri msg action quit ;;
    Suspend) systemctl suspend ;;
    Reboot) systemctl reboot ;;
    Shutdown) systemctl poweroff ;;
esac
