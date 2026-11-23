#!/usr/bin/env bash
set -euo pipefail

THEMES="$HOME/.config/themes"
WB="$HOME/.config/waybar"
KITTY="$HOME/.config/kitty"
ROFI="$HOME/.config/rofi"
NIRI="$HOME/.config/niri"
SWAYLOCK="$HOME/.config/swaylock"
MAKO="$HOME/.config/mako"

list_themes() {
    local dir
    for dir in "$THEMES"/*/; do
        [ -L "${dir%/}" ] && continue
        [ -f "$dir/meta.conf" ] && basename "$dir"
    done | sort
}

current_slug() {
    local target
    target="$(readlink "$THEMES/current" 2>/dev/null || true)"
    [ -n "$target" ] && basename "$target"
}

show_usage() {
    local cur
    cur="$(current_slug || true)"
    printf 'Current theme: %s\n' "${cur:-none}"
    printf 'Usage: %s <theme> | --next | --list\n\n' "${0##*/}"
    printf 'Available themes:\n'
    list_themes | sed 's/^/  /'
}

patch_calendar() {
    python3 - "$WB/config.jsonc" "$CAL_MONTH" "$CAL_DAY" "$CAL_WEEK" "$CAL_WEEKDAY" "$CAL_TODAY_FG" "$CAL_TODAY_BG" <<'PY'
import re
import sys

path, month, day, week, weekday, today_fg, today_bg = sys.argv[1:8]
with open(path, encoding="utf-8") as handle:
    text = handle.read()

def recolor(key, color):
    global text
    text = re.sub(
        r'("%s":\s*"<span color=\')#[0-9a-fA-F]{6}' % re.escape(key),
        lambda match: match.group(1) + color,
        text,
    )

recolor("months", month)
recolor("days", day)
recolor("weeks", week)
recolor("weekdays", weekday)
text = re.sub(
    r'("today":\s*"<span color=\')#[0-9a-fA-F]{6}(\' background=\')#[0-9a-fA-F]{6}',
    lambda match: match.group(1) + today_fg + match.group(2) + today_bg,
    text,
)

with open(path, "w", encoding="utf-8") as handle:
    handle.write(text)
PY
}

sync_gtk() {
    gsettings set org.gnome.desktop.interface gtk-theme "$GTK_THEME" 2>/dev/null || true
    gsettings set org.gnome.desktop.interface icon-theme "$ICON_THEME" 2>/dev/null || true

    local file
    for file in "$HOME/.config/gtk-3.0/settings.ini" "$HOME/.config/gtk-4.0/settings.ini"; do
        [ -f "$file" ] || continue
        sed -i -E "s|^gtk-theme-name=.*|gtk-theme-name=$GTK_THEME|" "$file"
        sed -i -E "s|^gtk-icon-theme-name=.*|gtk-icon-theme-name=$ICON_THEME|" "$file"
    done

    file="$HOME/.gtkrc-2.0"
    if [ -f "$file" ]; then
        sed -i -E "s|^gtk-theme-name=.*|gtk-theme-name=\"$GTK_THEME\"|" "$file"
        sed -i -E "s|^gtk-icon-theme-name=.*|gtk-icon-theme-name=\"$ICON_THEME\"|" "$file"
    fi

    file="$HOME/.config/xsettingsd/xsettingsd.conf"
    if [ -f "$file" ]; then
        sed -i -E "s|^Net/ThemeName .*|Net/ThemeName \"$GTK_THEME\"|" "$file"
        sed -i -E "s|^Net/IconThemeName .*|Net/IconThemeName \"$ICON_THEME\"|" "$file"
    fi

    pkill -HUP -x xsettingsd 2>/dev/null || true
}

reload_apps() {
    pkill -x waybar 2>/dev/null || true
    if command -v setsid >/dev/null 2>&1; then
        setsid -f waybar -c "$WB/config.jsonc" -s "$WB/style.css" >/dev/null 2>&1
    else
        nohup waybar -c "$WB/config.jsonc" -s "$WB/style.css" >/dev/null 2>&1 &
    fi
    pkill -USR1 -x kitty 2>/dev/null || true
    if command -v makoctl >/dev/null 2>&1 && pgrep -x mako >/dev/null 2>&1; then
        makoctl reload >/dev/null 2>&1 || true
    fi
}

apply_theme() {
    local slug="$1"
    local dir="$THEMES/$1"
    local sway_image=""
    local escaped=""

    if [ -L "${dir%/}" ] || [ ! -f "$dir/meta.conf" ]; then
        printf 'Unknown theme: %s\n' "$slug" >&2
        exit 1
    fi

    source "$dir/meta.conf"

    if [ -f "$SWAYLOCK/config" ]; then
        sway_image="$(sed -n 's/^image=//p' "$SWAYLOCK/config" | head -n 1)"
    fi

    cp "$dir/waybar.css" "$WB/style.css"
    cp "$dir/kitty.conf" "$KITTY/theme.conf"
    cp "$dir/rofi.rasi" "$ROFI/theme.rasi"
    cp "$dir/niri.kdl" "$NIRI/theme.kdl"
    cp "$dir/swaylock.conf" "$SWAYLOCK/config"
    mkdir -p "$MAKO"
    cp "$dir/mako.conf" "$MAKO/config"

    if [ -n "$sway_image" ]; then
        escaped="$(printf '%s' "$sway_image" | sed 's/[\\&|]/\\&/g')"
        sed -i -E "s|^image=.*|image=$escaped|" "$SWAYLOCK/config"
    fi

    ln -sfn "$dir" "$THEMES/current"

    if [ -f "$ROFI/config.rasi" ]; then
        sed -i -E "s|^([[:space:]]*icon-theme:[[:space:]]*)\"[^\"]*\"|\1\"$ICON_THEME\"|" "$ROFI/config.rasi"
    fi

    patch_calendar
    sync_gtk
    reload_apps

    printf 'Theme applied: %s (%s)\n' "$NAME" "$slug"
}

next_theme() {
    local -a themes=()
    local slug

    while IFS= read -r slug; do
        themes+=("$slug")
    done < <(list_themes)

    if [ "${#themes[@]}" -eq 0 ]; then
        printf 'No themes found\n' >&2
        exit 1
    fi

    local cur next i
    cur="$(current_slug || true)"
    next="${themes[0]}"

    if [ -n "$cur" ]; then
        for i in "${!themes[@]}"; do
            if [ "${themes[$i]}" = "$cur" ]; then
                next="${themes[$(((i + 1) % ${#themes[@]}))]}"
                break
            fi
        done
    fi

    apply_theme "$next"
}

case "${1:-}" in
    ""|--list|-l) show_usage ;;
    --next|-n) next_theme ;;
    -h|--help) show_usage ;;
    *) apply_theme "$1" ;;
esac
