#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/niri-rice"
STATE_FILE="$STATE_DIR/focus-mode"

mkdir -p "$STATE_DIR"

current() {
    if [ "$(cat "$STATE_FILE" 2>/dev/null || printf 'off')" = "on" ]; then
        printf 'on'
    else
        printf 'off'
    fi
}

write_state() {
    printf '%s\n' "$1" > "$STATE_FILE"
}

set_state() {
    local desired="$1"
    [ "$(current)" = "$desired" ] && return 0
    write_state "$desired"
    pkill -USR1 -x waybar 2>/dev/null || true
}

case "${1:-status}" in
    status) current ;;
    on) set_state on ;;
    off) set_state off ;;
    toggle)
        if [ "$(current)" = "on" ]; then
            set_state off
        else
            set_state on
        fi
        ;;
    reset) write_state off ;;
    *)
        printf 'Usage: %s {status|on|off|toggle|reset}\n' "${0##*/}" >&2
        exit 2
        ;;
esac
