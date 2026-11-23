#!/usr/bin/env bash
set -euo pipefail

THEMES="$HOME/.config/themes"

declare -A slug_of
names=()

for dir in "$THEMES"/*/; do
    [ -L "${dir%/}" ] && continue
    [ -f "$dir/meta.conf" ] || continue
    slug="$(basename "$dir")"
    name="$(source "$dir/meta.conf"; printf '%s' "$NAME")"
    slug_of["$name"]="$slug"
    names+=("$name")
done

if [ "${#names[@]}" -eq 0 ]; then
    printf 'No themes found\n' >&2
    exit 1
fi

mapfile -t sorted < <(printf '%s\n' "${names[@]}" | sort)

current_target="$(readlink "$THEMES/current" 2>/dev/null || true)"
current_slug=""
[ -n "$current_target" ] && current_slug="$(basename "$current_target")"

rofi_args=(-dmenu -i -p "Theme" -no-custom)
for name in "${sorted[@]}"; do
    if [ "${slug_of[$name]}" = "$current_slug" ]; then
        rofi_args+=(-select "$name")
        break
    fi
done

choice="$(printf '%s\n' "${sorted[@]}" | rofi "${rofi_args[@]}")" || exit 0
[ -n "$choice" ] || exit 0

exec "$THEMES/apply.sh" "${slug_of[$choice]}"
