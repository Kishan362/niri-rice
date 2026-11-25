#!/usr/bin/env bash
set -euo pipefail

CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"

set_ini_value() {
    local file="$1"
    local key="$2"
    local value="$3"
    local escaped

    escaped="$(printf '%s' "$value" | sed 's/[\\&|]/\\&/g')"
    if grep -q "^${key}=" "$file"; then
        sed -i -E "s|^${key}=.*|${key}=${escaped}|" "$file"
    else
        printf '%s=%s\n' "$key" "$value" >> "$file"
    fi
}

set_xsettings_value() {
    local file="$1"
    local key="$2"
    local value="$3"
    local escaped

    escaped="$(printf '%s' "$value" | sed 's/[\\&|]/\\&/g')"
    if grep -q "^${key}[[:space:]]" "$file"; then
        sed -i -E "s|^${key}[[:space:]].*|${key} \"${escaped}\"|" "$file"
    else
        printf '%s "%s"\n' "$key" "$value" >> "$file"
    fi
}

gtk_sync() {
    local gtk_theme="${1:-}"
    local icon_theme="${2:-}"
    local file

    if [ -n "$gtk_theme" ]; then
        gsettings set org.gnome.desktop.interface gtk-theme "$gtk_theme" 2>/dev/null || true
    fi
    if [ -n "$icon_theme" ]; then
        gsettings set org.gnome.desktop.interface icon-theme "$icon_theme" 2>/dev/null || true
    fi

    for file in "$CONFIG_HOME/gtk-3.0/settings.ini" "$CONFIG_HOME/gtk-4.0/settings.ini"; do
        [ -f "$file" ] || continue
        if [ -n "$gtk_theme" ]; then
            set_ini_value "$file" gtk-theme-name "$gtk_theme"
        fi
        if [ -n "$icon_theme" ]; then
            set_ini_value "$file" gtk-icon-theme-name "$icon_theme"
        fi
    done

    file="$HOME/.gtkrc-2.0"
    if [ -f "$file" ]; then
        if [ -n "$gtk_theme" ]; then
            set_ini_value "$file" gtk-theme-name "\"$gtk_theme\""
        fi
        if [ -n "$icon_theme" ]; then
            set_ini_value "$file" gtk-icon-theme-name "\"$icon_theme\""
        fi
    fi

    file="$CONFIG_HOME/xsettingsd/xsettingsd.conf"
    if [ -f "$file" ]; then
        if [ -n "$gtk_theme" ]; then
            set_xsettings_value "$file" Net/ThemeName "$gtk_theme"
        fi
        if [ -n "$icon_theme" ]; then
            set_xsettings_value "$file" Net/IconThemeName "$icon_theme"
        fi
    fi

    pkill -HUP -x xsettingsd 2>/dev/null || true
}

case "${1:-}" in
    apply)
        if [ "$#" -lt 2 ]; then
            printf 'Usage: %s apply <gtk-theme> [icon-theme]\n' "${0##*/}" >&2
            exit 2
        fi
        gtk_sync "$2" "${3:-}"
        ;;
    icon)
        if [ "$#" -lt 2 ]; then
            printf 'Usage: %s icon <icon-theme>\n' "${0##*/}" >&2
            exit 2
        fi
        gtk_sync "" "$2"
        ;;
    *)
        printf 'Usage: %s {apply <gtk-theme> [icon-theme]|icon <icon-theme>}\n' "${0##*/}" >&2
        exit 2
        ;;
esac
