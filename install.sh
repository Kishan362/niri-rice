#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_SRC="$REPO_DIR/config"
WALLPAPER_SRC="$REPO_DIR/wallpapers"
ZSHRC_SRC="$REPO_DIR/zshrc"
THEME="everforest-dark"
WALLPAPER="green.png"
DRY_RUN=0
BACKUP_DIR="$HOME/.rice-backup-$(date +%Y%m%d-%H%M%S)"

usage() {
    printf 'Usage: %s [options]\n\n' "${0##*/}"
    printf 'Options:\n'
    printf '  --theme <name>       Theme to apply (default: %s)\n' "$THEME"
    printf '  --wallpaper <file>   Wallpaper from wallpapers/ (default: %s)\n' "$WALLPAPER"
    printf '  --dry-run            Show actions without changing files\n'
    printf '  -h, --help           Show this help\n'
}

os_release_field() {
    local key="$1"
    [ -r /etc/os-release ] || return 0
    sed -n "s/^$key=//p" /etc/os-release | head -n 1 | tr -d '"'
}

print_arch_hint() {
    printf 'Official Arch/CachyOS repositories:\n' >&2
    printf '  sudo pacman -S niri waybar kitty rofi mako swaylock python python-gobject gtk4 libadwaita awww grim imagemagick brightnessctl pamixer playerctl cliphist wl-clipboard pavucontrol polkit-gnome gammastep ttf-jetbrains-mono-nerd noto-fonts tela-circle-icon-theme-all gnome-themes-extra materia-gtk-theme\n' >&2
    printf 'Optional AUR visuals (use paru or yay):\n' >&2
    printf '  paru -S catppuccin-gtk-theme-mocha bibata-cursor-theme-bin nordic-theme\n' >&2
    printf 'Optional official packages: btop nwg-look xsettingsd swaybg\n' >&2
    printf 'Optional AUR package: zen-browser-bin\n' >&2
}

print_gentoo_hint() {
    cat >&2 <<'EOF'
Gentoo packages (GURU is required for niri and several tools):

  sudo emerge --ask app-eselect/eselect-repository dev-vcs/git
  sudo eselect repository enable guru
  sudo emerge --sync guru
  printf '%s\n' '*/*::guru ~amd64' | sudo tee /etc/portage/package.accept_keywords/guru >/dev/null

Replace ~amd64 with ~arm64 on arm64 systems.

Recommended USE flags:

  printf '%s\n' 'gui-apps/waybar niri mpris network pulseaudio tray upower' 'x11-misc/rofi wayland' 'media-fonts/nerdfonts jetbrainsmono' | sudo tee /etc/portage/package.use/niri-rice >/dev/null

Main packages:

  sudo emerge --ask gui-wm/niri gui-apps/waybar x11-terms/kitty x11-misc/rofi \
    gui-apps/mako gui-apps/swaylock dev-python/pygobject gui-libs/gtk \
    gui-libs/libadwaita gui-apps/awww gui-apps/grim media-gfx/imagemagick \
    app-misc/brightnessctl media-sound/pamixer media-sound/playerctl \
    app-misc/cliphist gui-apps/wl-clipboard media-sound/pavucontrol \
    mate-extra/mate-polkit x11-misc/gammastep media-fonts/noto \
    x11-themes/tela-icon-theme

Optional themes and visuals:

  sudo emerge --ask x11-themes/catppuccin-gtk x11-themes/bibata-xcursors \
    x11-themes/materia-theme media-fonts/nerdfonts

Optional tools:

  sudo emerge --ask sys-process/btop app-misc/nwg-look x11-misc/xsettingsd gui-apps/swaybg

OpenRC:

  sudo emerge --ask sys-auth/elogind
  sudo rc-update add elogind boot
  Start niri with: dbus-run-session niri --session

Tela Circle icons are not provided by x11-themes/tela-icon-theme. Install:
https://github.com/vinceliuice/Tela-circle-icon-theme
EOF
}

print_generic_hint() {
    printf 'Install the missing commands with your distribution package manager, then rerun the installer.\n' >&2
}

print_package_hint() {
    local distro_id="$1"
    local distro_like="$2"
    case "$distro_id" in
        gentoo)
            print_gentoo_hint
            ;;
        arch|archarm|cachyos|endeavouros|garuda|manjaro)
            print_arch_hint
            ;;
        *)
            if printf '%s' "$distro_like" | grep -qw arch; then
                print_arch_hint
            else
                print_generic_hint
            fi
            ;;
    esac
}

run() {
    if [ "$DRY_RUN" -eq 1 ]; then
        printf '[dry-run] %s\n' "$*"
    else
        "$@"
    fi
}

backup_item() {
    local path="$1"
    local rel
    [ -e "$path" ] || return 0
    rel="${path#"$HOME"/}"
    run mkdir -p "$BACKUP_DIR/$(dirname "$rel")"
    run cp -a "$path" "$BACKUP_DIR/$rel"
}

copy_tree() {
    local src="$1"
    local dest="$2"
    run mkdir -p "$dest"
    run cp -a "$src/." "$dest/"
}

rewrite_install_paths() {
    local file="$1"
    local escaped_home
    [ -f "$file" ] || return 0
    grep -q '/home/lk' "$file" || return 0
    escaped_home="$(printf '%s' "$HOME" | sed 's/[\\&|]/\\&/g')"
    run sed -i "s|/home/lk|$escaped_home|g" "$file"
}

sync_swaylock() {
    local image="$1"
    local escaped
    local config="$HOME/.config/swaylock/config"
    [ -f "$config" ] || return 0
    escaped="$(printf '%s' "$image" | sed 's/[\\&|]/\\&/g')"
    if grep -q '^image=' "$config"; then
        run sed -i -E "s|^image=.*|image=$escaped|" "$config"
    elif [ "$DRY_RUN" -eq 1 ]; then
        printf '[dry-run] append image=%s to %s\n' "$image" "$config"
    else
        printf 'image=%s\n' "$image" >> "$config"
    fi
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --theme)
            THEME="${2:?--theme requires a theme name}"
            shift 2
            ;;
        --wallpaper)
            WALLPAPER="${2:?--wallpaper requires a file name}"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf 'Unknown option: %s\n' "$1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

missing=()
for cmd in niri waybar kitty rofi mako swaylock python3; do
    command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
done

if [ "${#missing[@]}" -gt 0 ]; then
    printf 'Missing required commands: %s\n' "${missing[*]}" >&2
    print_package_hint "$(os_release_field ID)" "$(os_release_field ID_LIKE)"
    exit 1
fi

for cmd in grim magick brightnessctl pamixer playerctl cliphist wl-copy wl-paste pavucontrol gammastep btop gsettings zen-browser dbus-update-activation-environment; do
    command -v "$cmd" >/dev/null 2>&1 || printf 'Warning: optional command missing: %s\n' "$cmd" >&2
done

if ! python3 -c 'import gi; gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")' >/dev/null 2>&1; then
    printf 'Warning: GTK4/libadwaita Python bindings not found; Appearance window will fall back to Rofi\n' >&2
fi

if ! command -v awww >/dev/null 2>&1 && ! command -v swww >/dev/null 2>&1 && ! command -v swaybg >/dev/null 2>&1; then
    printf 'Warning: no wallpaper backend found (awww, swww, or swaybg)\n' >&2
fi

polkit_found=0
for agent in \
    /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1 \
    /usr/libexec/polkit-gnome-authentication-agent-1 \
    /usr/libexec/polkit-mate-authentication-agent-1; do
    if [ -x "$agent" ]; then
        polkit_found=1
    fi
done
[ "$polkit_found" -eq 1 ] || \
    printf 'Warning: polkit authentication agent not found\n' >&2

if [ ! -f "$CONFIG_SRC/themes/$THEME/meta.conf" ]; then
    printf 'Unknown theme: %s\nAvailable themes:\n' "$THEME" >&2
    for dir in "$CONFIG_SRC"/themes/*/; do
        [ -f "$dir/meta.conf" ] && basename "$dir"
    done | sort | sed 's/^/  /' >&2
    exit 1
fi

source "$CONFIG_SRC/themes/$THEME/meta.conf"

gtk_found=0
for base in "$HOME/.themes" "$HOME/.local/share/themes" /usr/share/themes; do
    [ -d "$base/$GTK_THEME" ] && gtk_found=1
done
[ "$gtk_found" -eq 1 ] || printf 'Warning: GTK theme not found: %s\n' "$GTK_THEME" >&2

icon_found=0
for base in "$HOME/.icons" "$HOME/.local/share/icons" /usr/share/icons; do
    [ -d "$base/$ICON_THEME" ] && icon_found=1
done
[ "$icon_found" -eq 1 ] || printf 'Warning: icon theme not found: %s\n' "$ICON_THEME" >&2

cursor_theme="$(sed -n 's/^gtk-cursor-theme-name=//p' "$CONFIG_SRC/gtk-3.0/settings.ini" | head -n 1)"
if [ -n "$cursor_theme" ]; then
    cursor_found=0
    for base in "$HOME/.icons" "$HOME/.local/share/icons" /usr/share/icons; do
        [ -d "$base/$cursor_theme" ] && cursor_found=1
    done
    [ "$cursor_found" -eq 1 ] || printf 'Warning: cursor theme not found: %s\n' "$cursor_theme" >&2
fi

if command -v fc-match >/dev/null 2>&1; then
    fc-match 'JetBrainsMono Nerd Font' | grep -q 'JetBrainsMono Nerd Font' || \
        printf 'Warning: JetBrainsMono Nerd Font not found\n' >&2
    fc-match 'Noto Sans' | grep -q 'Noto Sans' || \
        printf 'Warning: Noto Sans not found\n' >&2
fi

if [ ! -f "$WALLPAPER_SRC/$WALLPAPER" ]; then
    printf 'Wallpaper not found: %s\n' "$WALLPAPER" >&2
    exit 1
fi

for rel in \
    .config/niri \
    .config/waybar \
    .config/kitty \
    .config/rofi \
    .config/themes \
    .config/wallpaper \
    .config/mako \
    .config/swaylock \
    .config/gtk-3.0 \
    .config/gtk-4.0 \
    .config/xsettingsd \
    .zshrc \
    .local/share/applications/rice-settings.desktop; do
    backup_item "$HOME/$rel"
done

copy_tree "$CONFIG_SRC/niri" "$HOME/.config/niri"
copy_tree "$CONFIG_SRC/waybar" "$HOME/.config/waybar"
copy_tree "$CONFIG_SRC/kitty" "$HOME/.config/kitty"
copy_tree "$CONFIG_SRC/rofi" "$HOME/.config/rofi"
copy_tree "$CONFIG_SRC/themes" "$HOME/.config/themes"
copy_tree "$CONFIG_SRC/wallpaper" "$HOME/.config/wallpaper"
copy_tree "$CONFIG_SRC/mako" "$HOME/.config/mako"
copy_tree "$CONFIG_SRC/swaylock" "$HOME/.config/swaylock"
copy_tree "$CONFIG_SRC/gtk-3.0" "$HOME/.config/gtk-3.0"
copy_tree "$CONFIG_SRC/gtk-4.0" "$HOME/.config/gtk-4.0"
copy_tree "$CONFIG_SRC/xsettingsd" "$HOME/.config/xsettingsd"
rewrite_install_paths "$HOME/.config/niri/config.kdl"
run cp -a "$ZSHRC_SRC" "$HOME/.zshrc"

settings_exec="$(printf '%s' "$HOME/.config/themes/settings.sh" | sed 's/[\\&|]/\\&/g')"
settings_launcher="$HOME/.local/share/applications/rice-settings.desktop"
if [ "$DRY_RUN" -eq 1 ]; then
    printf '[dry-run] write %s\n' "$settings_launcher"
else
    mkdir -p "$(dirname "$settings_launcher")"
    sed "s|@SETTINGS@|$settings_exec|" "$CONFIG_SRC/applications/rice-settings.desktop.in" > "$settings_launcher"
fi

run mkdir -p "$HOME/Pictures/Wallpapers"
while IFS= read -r -d '' file; do
    run cp -n "$file" "$HOME/Pictures/Wallpapers/"
done < <(find "$WALLPAPER_SRC" -maxdepth 1 -type f -print0)

run chmod +x "$HOME/.config/themes/apply.sh" "$HOME/.config/themes/menu.sh" "$HOME/.config/themes/settings.sh" "$HOME/.config/themes/gtk-theme.sh" "$HOME/.config/rofi/power-menu.sh" "$HOME/.config/niri/polkit-agent.sh" "$HOME/.config/niri/session-env.sh" "$HOME/.config/waybar/scripts/waybar-style.py"
run find "$HOME/.config/wallpaper" "$HOME/.config/waybar/scripts" -type f -name '*.sh' -exec chmod +x {} +

run "$HOME/.config/themes/apply.sh" "$THEME"

wallpaper_path="$HOME/Pictures/Wallpapers/$WALLPAPER"
state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/wallpaper"
run mkdir -p "$state_dir"
if [ "$DRY_RUN" -eq 1 ]; then
    printf '[dry-run] write %s to %s/current\n' "$wallpaper_path" "$state_dir"
else
    printf '%s\n' "$wallpaper_path" > "$state_dir/current"
fi
sync_swaylock "$wallpaper_path"

if [ "$DRY_RUN" -eq 0 ] && [ -f "$wallpaper_path" ]; then
    if command -v awww >/dev/null 2>&1 && ! awww query >/dev/null 2>&1; then
        if command -v setsid >/dev/null 2>&1; then
            setsid -f awww-daemon >/dev/null 2>&1 || true
        else
            nohup awww-daemon >/dev/null 2>&1 &
        fi
        sleep 0.5
    elif command -v swww >/dev/null 2>&1 && ! swww query >/dev/null 2>&1; then
        if command -v setsid >/dev/null 2>&1; then
            setsid -f swww-daemon >/dev/null 2>&1 || true
        else
            nohup swww-daemon >/dev/null 2>&1 &
        fi
        sleep 0.5
    fi
    if command -v awww >/dev/null 2>&1 || command -v swww >/dev/null 2>&1 || command -v swaybg >/dev/null 2>&1; then
        "$HOME/.config/wallpaper/wallpaper.sh" "$wallpaper_path" || \
            printf 'Warning: could not apply wallpaper\n' >&2
    else
        printf 'Warning: no wallpaper backend found (awww, swww, or swaybg)\n' >&2
    fi
elif [ "$DRY_RUN" -eq 1 ]; then
    printf '[dry-run] %s %s\n' "$HOME/.config/wallpaper/wallpaper.sh" "$wallpaper_path"
fi

if [ "$DRY_RUN" -eq 0 ] && command -v niri >/dev/null 2>&1; then
    niri validate || printf 'Warning: niri config validation failed\n' >&2
fi

if [ "$DRY_RUN" -eq 1 ]; then
    printf '\nDry run complete; no files were changed.\n'
    exit 0
fi

printf '\nRice installed.\n'
printf '  Theme: %s\n' "$THEME"
printf '  Wallpaper: %s\n' "$WALLPAPER"
if [ -d "$BACKUP_DIR" ]; then
    printf '  Backup: %s\n' "$BACKUP_DIR"
fi
printf 'Log out and back in if niri does not reload automatically.\n'
