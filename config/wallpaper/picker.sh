#!/usr/bin/env bash
set -euo pipefail

WALL_DIR="$HOME/Pictures/Wallpapers"
WALLPAPER="$HOME/.config/wallpaper/wallpaper.sh"
THUMB_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/wallpaper-thumbs"

mkdir -p "$THUMB_DIR"

declare -A thumb_of
entries=()

while IFS= read -r rel; do
    src="$WALL_DIR/$rel"
    key="$(printf '%s' "$src" | md5sum | cut -d' ' -f1)"
    thumb="$THUMB_DIR/$key.png"

    if [ ! -f "$thumb" ] || [ "$src" -nt "$thumb" ]; then
        if command -v magick >/dev/null 2>&1; then
            magick "$src[0]" -thumbnail '480x270^' -gravity center -extent 480x270 "$thumb" 2>/dev/null || continue
        else
            cp -f "$src" "$thumb" 2>/dev/null || continue
        fi
    fi

    entries+=("$rel")
    thumb_of["$rel"]="$thumb"
done < <("$WALLPAPER" --list)

if [ "${#entries[@]}" -eq 0 ]; then
    notify-send "Wallpaper" "No images found in $WALL_DIR" 2>/dev/null || printf 'No images found in %s\n' "$WALL_DIR" >&2
    exit 1
fi

current="$("$WALLPAPER" --current || true)"
current_rel=""
case "$current" in
    "$WALL_DIR"/*) current_rel="${current#"$WALL_DIR"/}" ;;
esac

rofi_args=(-dmenu -i -p "Wallpaper" -show-icons -no-custom)
[ -n "$current_rel" ] && rofi_args+=(-select "$current_rel")

choice="$(
    for rel in "${entries[@]}"; do
        printf '%s\000icon\037%s\n' "$rel" "${thumb_of[$rel]}"
    done | rofi "${rofi_args[@]}" \
        -theme-str 'element-icon { size: 72px; } listview { lines: 6; } window { width: 640px; }'
)" || exit 0

[ -n "$choice" ] || exit 0
"$WALLPAPER" "$WALL_DIR/$choice"
