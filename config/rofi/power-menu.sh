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

power_action() {
    local action="$1"

    if [ -d /run/systemd/system ] && command -v systemctl >/dev/null 2>&1; then
        systemctl "$action"
    elif command -v loginctl >/dev/null 2>&1; then
        loginctl "$action"
    elif [ "$action" = "suspend" ] && command -v zzz >/dev/null 2>&1; then
        zzz
    elif [ "$action" != "suspend" ] && command -v openrc-shutdown >/dev/null 2>&1; then
        case "$action" in
            reboot) openrc-shutdown --reboot now ;;
            poweroff) openrc-shutdown --poweroff now ;;
        esac
    else
        printf 'No supported power manager found for: %s\n' "$action" >&2
        exit 1
    fi
}

case "$choice" in
    Lock) swaylock --indicator-idle-visible ;;
    Logout) niri msg action quit ;;
    Suspend) power_action suspend ;;
    Reboot) power_action reboot ;;
    Shutdown) power_action poweroff ;;
esac
