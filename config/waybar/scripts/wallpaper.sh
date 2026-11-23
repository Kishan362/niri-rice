#!/usr/bin/env bash
set -euo pipefail

current="$("$HOME/.config/wallpaper/wallpaper.sh" --current 2>/dev/null || true)"
name=""

[ -n "$current" ] && name="$(basename "$current")"
[ -n "$name" ] || name="None"

printf '{"text":"󰸉","tooltip":"Wallpaper: %s\\nLeft-click: pick wallpaper · Right-click: next"}\n' "$name"
