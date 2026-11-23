#!/usr/bin/env bash
set -euo pipefail

WALL_DIR="$HOME/Pictures/Wallpapers"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/wallpaper"
STATE_FILE="$STATE_DIR/current"
SWAYLOCK_CONFIG="$HOME/.config/swaylock/config"

list_images() {
    find "$WALL_DIR" -type f \
        \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' \
        -o -iname '*.webp' -o -iname '*.gif' -o -iname '*.bmp' \) \
        -printf '%P\n' | sort
}

sync_swaylock() {
    local file="$1" escaped
    [ -f "$SWAYLOCK_CONFIG" ] || return 0
    escaped="$(printf '%s' "$file" | sed 's/[\\&|]/\\&/g')"
    sed -i -E "s|^image=.*|image=$escaped|" "$SWAYLOCK_CONFIG"
}

set_wallpaper() {
    local file="$1"

    if [ ! -f "$file" ]; then
        printf 'Wallpaper not found: %s\n' "$file" >&2
        exit 1
    fi

    if command -v awww >/dev/null 2>&1; then
        awww img "$file" --transition-type grow --transition-pos center --transition-duration 0.8 --resize crop
    elif command -v swww >/dev/null 2>&1; then
        swww img "$file" --transition-type grow --transition-pos center --transition-duration 0.8
    elif command -v swaybg >/dev/null 2>&1; then
        pkill -x swaybg 2>/dev/null || true
        if command -v setsid >/dev/null 2>&1; then
            setsid -f swaybg -i "$file" -m fill >/dev/null 2>&1
        else
            nohup swaybg -i "$file" -m fill >/dev/null 2>&1 &
        fi
    else
        printf 'No awww, swww, or swaybg CLI available\n' >&2
        exit 1
    fi

    mkdir -p "$STATE_DIR"
    printf '%s\n' "$file" > "$STATE_FILE"
    sync_swaylock "$file"
}

current_wallpaper() {
    if [ -f "$STATE_FILE" ]; then
        head -n 1 "$STATE_FILE"
        return 0
    fi

    if command -v awww >/dev/null 2>&1; then
        awww query 2>/dev/null | sed -n 's/.*currently displaying: image: //p' | head -n 1
    fi
}

next_wallpaper() {
    local -a images=()
    local rel cur next i

    mapfile -t images < <(list_images)
    if [ "${#images[@]}" -eq 0 ]; then
        printf 'No wallpapers found in %s\n' "$WALL_DIR" >&2
        exit 1
    fi

    cur="$(current_wallpaper || true)"
    next="${images[0]}"

    if [ -n "$cur" ]; then
        for i in "${!images[@]}"; do
            if [ "$WALL_DIR/${images[$i]}" = "$cur" ]; then
                next="${images[$(((i + 1) % ${#images[@]}))]}"
                break
            fi
        done
    fi

    set_wallpaper "$WALL_DIR/$next"
}

random_wallpaper() {
    local -a images=()

    mapfile -t images < <(list_images)
    if [ "${#images[@]}" -eq 0 ]; then
        printf 'No wallpapers found in %s\n' "$WALL_DIR" >&2
        exit 1
    fi

    set_wallpaper "$WALL_DIR/$(printf '%s\n' "${images[@]}" | shuf -n 1)"
}

case "${1:-}" in
    ""|--help|-h)
        printf 'Usage: %s <file|--next|--random|--current|--list>\n' "${0##*/}"
        ;;
    --next|-n) next_wallpaper ;;
    --random|-r) random_wallpaper ;;
    --current|-c) current_wallpaper ;;
    --list|-l) list_images ;;
    *)
        if [ -f "$1" ]; then
            set_wallpaper "$1"
        elif [ -f "$WALL_DIR/$1" ]; then
            set_wallpaper "$WALL_DIR/$1"
        else
            printf 'Wallpaper not found: %s\n' "$1" >&2
            exit 1
        fi
        ;;
esac
