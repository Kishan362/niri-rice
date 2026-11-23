#!/usr/bin/env bash
set -euo pipefail

THEMES="$HOME/.config/themes"

target="$(readlink "$THEMES/current" 2>/dev/null || true)"
name=""
if [ -n "$target" ] && [ -f "$target/meta.conf" ]; then
    name="$(source "$target/meta.conf"; printf '%s' "$NAME")"
fi
[ -n "$name" ] || name="Unknown"

printf '{"text":"󰏘","tooltip":"Theme: %s\\nLeft-click: pick theme · Right-click: next"}\n' "$name"
