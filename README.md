# Niri Everforest Rice

A Niri + Waybar rice with a centered clock, themed notifications, an Appearance settings window, a wallpaper picker, a rofi power menu, and twenty-six switchable color themes.

![Preview](screenshots/preview.png)

## Included

- Niri configuration with rounded corners, blur, animations, and workspace binds
- Waybar notch with numbered workspace chips, MPRIS, clock, system stats, microphone, nightlight, caffeine, battery, tray, wallpaper, theme, and power controls
- Appearance window with rice theme cards, a GTK-only theme browser, wallpaper thumbnails, Waybar transparency/color/alignment controls, a focus-mode switch, and GTK/icon shortcuts
- Theme switcher that syncs Waybar, Niri, Kitty, Rofi, GTK, icons, Zsh prompt, Swaylock, and Mako
- Wallpaper picker with thumbnails and next/random controls
- Rofi power menu and themed notifications
- Kitty, Rofi, Swaylock, and Mako theme assets
- Included wallpapers and a preview screenshot

The default theme is `everforest-dark` and the default wallpaper is `green.png`.

Tested on Arch Linux with Niri 26.04, Waybar 0.16, Kitty 0.51, Rofi 2.1, and Mako 1.11. Gentoo instructions target the current GURU/OpenRC packages but have not been boot-tested on a Gentoo host.

## Requirements

### Arch Linux / CachyOS

Install the official packages first:

```bash
sudo pacman -S niri waybar kitty rofi mako swaylock python python-gobject gtk4 \
  libadwaita awww grim imagemagick brightnessctl pamixer playerctl cliphist \
  wl-clipboard pavucontrol polkit-gnome gammastep ttf-jetbrains-mono-nerd \
  noto-fonts tela-circle-icon-theme-all gnome-themes-extra materia-gtk-theme
```

Optional official packages:

```bash
sudo pacman -S btop nwg-look xsettingsd swaybg
```

The Catppuccin GTK theme, Nordic GTK theme, and Bibata cursor are AUR packages on vanilla Arch:

```bash
paru -S catppuccin-gtk-theme-mocha nordic-theme bibata-cursor-theme-bin
```

Zen Browser is optional and also AUR:

```bash
paru -S zen-browser-bin
```

Use `yay` instead of `paru` if that is your AUR helper. CachyOS may provide some of these packages in its own repositories, so only install from the AUR if `pacman` cannot find them.

### Gentoo Linux

Niri and several optional tools are in GURU. Enable the repository, accept the GURU keyword, and add the recommended USE flags:

```bash
sudo emerge --ask app-eselect/eselect-repository dev-vcs/git
sudo eselect repository enable guru
sudo emerge --sync guru
echo '*/*::guru ~amd64' | sudo tee /etc/portage/package.accept_keywords/guru
```

Use `~arm64` instead of `~amd64` on ARM64 systems. The `*/*::guru` keyword applies to the whole overlay; narrow it to individual packages if you prefer.

Recommended USE flags:

```bash
sudo tee /etc/portage/package.use/niri-rice >/dev/null <<'EOF'
gui-apps/waybar niri mpris network pulseaudio tray upower
x11-misc/rofi wayland
media-fonts/nerdfonts jetbrainsmono
EOF
```

Install the core packages:

```bash
sudo emerge --ask gui-wm/niri gui-apps/waybar x11-terms/kitty x11-misc/rofi \
  gui-apps/mako gui-apps/swaylock dev-python/pygobject gui-libs/gtk \
  gui-libs/libadwaita gui-apps/awww gui-apps/grim media-gfx/imagemagick \
  app-misc/brightnessctl media-sound/pamixer media-sound/playerctl \
  app-misc/cliphist gui-apps/wl-clipboard media-sound/pavucontrol \
  mate-extra/mate-polkit x11-misc/gammastep media-fonts/noto \
  x11-themes/tela-icon-theme
```

Optional themes, cursors, fonts, and tools:

```bash
sudo emerge --ask x11-themes/catppuccin-gtk x11-themes/bibata-xcursors \
  x11-themes/materia-theme media-fonts/nerdfonts
sudo emerge --ask sys-process/btop app-misc/nwg-look x11-misc/xsettingsd gui-apps/swaybg
```

`x11-themes/tela-icon-theme` installs Tela, not Tela Circle. For the default Tela-circle names, install upstream:

```bash
git clone https://github.com/vinceliuice/Tela-circle-icon-theme.git
cd Tela-circle-icon-theme
./install.sh -a
```

OpenRC users also need elogind:

```bash
sudo emerge --ask sys-auth/elogind
sudo rc-update add elogind boot
```

Start Niri with `dbus-run-session niri --session`. The `niri-session` wrapper is systemd-specific. If you use a display manager, make its Niri desktop file run `niri --session`. The installer provides OpenRC-compatible polkit and D-Bus startup helpers, and the power menu detects `systemctl`, `loginctl`, or `openrc-shutdown`.

The rice uses Catppuccin, Materia, Nordic, and Adwaita GTK themes, the Tela Circle icon set, Bibata cursor, JetBrainsMono Nerd Font, and Noto Sans. These are not bundled in this repository. Missing optional visuals produce warnings; the installer still completes and applications use fallback themes.

## Install

```bash
git clone https://github.com/Kishan362/niri-rice.git
cd niri-rice
./install.sh
```

Choose a different theme or wallpaper:

```bash
./install.sh --theme catppuccin-mocha --wallpaper grovebox.png
```

Preview the changes without touching any files:

```bash
./install.sh --dry-run
```

The installer backs up existing files to `~/.rice-backup-<timestamp>` before copying. Wallpapers already present in `~/Pictures/Wallpapers` are not overwritten. It also installs the included `zshrc` as `~/.zshrc`.

Log out and back in if Niri does not reload automatically.

## Keybinds

| Keys | Action |
| --- | --- |
| `Alt+Return` | Open Kitty |
| `Mod+D` | Open Rofi launcher |
| `Mod+Z` | Open Zen Browser |
| `Alt+T` | Appearance settings |
| `Alt+W` | Wallpaper picker |
| `Alt+Shift+W` | Next wallpaper |
| `Super+Alt+L` | Lock screen |
| `Alt+F` | Toggle Focus Mode (workspace, tray, mic) |
| `Print` | Screenshot |
| `Mod+O` | Overview |
| `Mod+Q` | Close window |
| `Mod+Shift+E` | Quit Niri |

## Themes

Open the Appearance window with `Alt+T`, the Waybar theme button, or the **Appearance** app launcher. It has five pages:

- **Themes**: searchable full-rice cards, including thirteen Catppuccin Mocha accent variants; click a card to apply it.
- **GTK**: browser for installed GTK themes, with an icon-theme selector. Applying here changes GTK/icons only.
- **Wallpaper**: thumbnail grid with current wallpaper, random, and next controls.
- **Waybar**: bar/pill transparency, background and text colors, corner radii, and module text alignment.
- **System**: current GTK/icon/cursor/font values, focus-mode switch, and folder shortcuts.

Waybar tweaks are saved in `~/.config/waybar/waybar-settings.json` and survive theme changes. **Reset appearance** returns the bar to the current theme defaults. Catppuccin accent cards apply the matching GTK theme and icon theme; the GTK page excludes those accents to avoid duplicate entries.

If GTK4/libadwaita Python bindings are unavailable, `Alt+T` falls back to the Rofi theme picker. Themes can also be applied directly:

```bash
~/.config/themes/apply.sh <theme>
```

List themes:

```bash
~/.config/themes/apply.sh --list
```

Cycle themes:

```bash
~/.config/themes/apply.sh --next
```

Each theme directory contains Waybar CSS, Kitty colors, Rofi styles, a Zsh prompt, Niri colors, Swaylock colors, Mako notification styling, and metadata.

## Notes

- Mako notifications follow the active theme, including icons and critical notification borders.
- The Glass macOS theme keeps translucent notifications but does not blur behind them. Mako uses a full-screen layer surface, so Niri blur would blur the entire desktop.
- If notifications are not running, start Mako with:

```bash
systemctl --user enable --now mako.service
```

- On OpenRC, start `mako` from your Niri session instead, for example by adding `spawn-at-startup "mako"` to `~/.config/niri/config.kdl`.

- Wallpapers are included for convenience. Replace them with your own images in `~/Pictures/Wallpapers` and check their licenses before redistributing.
- The installer requires a graphical Wayland session for the final wallpaper step. It uses `awww` when available, then `swww`, then `swaybg`. If the selected daemon is not running, it will try to start it.

## Publish to GitHub

Create an empty repository on GitHub, then:

```bash
cd ~/niri-rice
git init -b main
git add .
git commit -m "Initial rice"
git remote add origin git@github.com:YOUR-USER/niri-rice.git
git push -u origin main
```

With GitHub CLI:

```bash
cd ~/niri-rice
git init -b main
git add .
git commit -m "Initial rice"
gh repo create niri-rice --public --source=. --remote=origin --push
```
