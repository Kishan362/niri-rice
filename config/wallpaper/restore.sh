#!/usr/bin/env bash
set -euo pipefail

WALLPAPER="$HOME/.config/wallpaper/wallpaper.sh"

if command -v awww >/dev/null 2>&1; then
    for _ in $(seq 1 50); do
        awww query >/dev/null 2>&1 && break
        sleep 0.1
    done
elif command -v swww >/dev/null 2>&1; then
    for _ in $(seq 1 50); do
        swww query >/dev/null 2>&1 && break
        sleep 0.1
    done
fi

current="$("$WALLPAPER" --current || true)"
if [ -n "$current" ] && [ -f "$current" ]; then
    "$WALLPAPER" "$current"
    exit 0
fi

"$WALLPAPER" --next
