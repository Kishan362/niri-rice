#!/usr/bin/env python3

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Pango", "1.0")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango

HOME = Path.home()
CONFIG_DIR = Path(__file__).resolve().parent.parent
THEMES_DIR = CONFIG_DIR / "themes"
WAYBAR_DIR = CONFIG_DIR / "waybar"
LIVE_WAYBAR_DIR = HOME / ".config" / "waybar"
WAYBAR_STYLE_SCRIPT = LIVE_WAYBAR_DIR / "scripts" / "waybar-style.py"
WAYBAR_SETTINGS_FILE = LIVE_WAYBAR_DIR / "waybar-settings.json"
WALLPAPER_SCRIPT = CONFIG_DIR / "wallpaper" / "wallpaper.sh"
FOCUS_SCRIPT = LIVE_WAYBAR_DIR / "scripts" / "focus.sh"

if not WAYBAR_STYLE_SCRIPT.is_file():
    WAYBAR_STYLE_SCRIPT = WAYBAR_DIR / "scripts" / "waybar-style.py"
if not FOCUS_SCRIPT.is_file():
    FOCUS_SCRIPT = WAYBAR_DIR / "scripts" / "focus.sh"
WALLPAPER_DIR = HOME / "Pictures" / "Wallpapers"
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", HOME / ".local" / "state"))
FOCUS_STATE = STATE_DIR / "niri-rice" / "focus-mode"
THUMB_DIR = Path(os.environ.get("XDG_CACHE_HOME", HOME / ".cache")) / "wallpaper-thumbs"
GTK_THEME_SCRIPT = THEMES_DIR / "gtk-theme.sh"
GTK_THEME_DIRS = (HOME / ".themes", Path("/usr/share/themes"))
ICON_THEME_DIRS = (HOME / ".icons", HOME / ".local/share/icons", Path("/usr/share/icons"))
GTK_SKIP_SUFFIXES = ("-hdpi", "-xhdpi", "-compact")


def read_meta(path):
    data = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
        if not match:
            continue
        value = match.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        data[match.group(1)] = value
    return data


def theme_palette(theme_dir, meta):
    values = {}
    rasi = theme_dir / "rofi.rasi"
    if rasi.is_file():
        for match in re.finditer(r"^\s*([A-Za-z0-9_-]+)\s*:\s*([^;]+);", rasi.read_text(encoding="utf-8"), re.M):
            values[match.group(1)] = match.group(2).strip()

    def resolve(value, depth=0):
        value = (value or "").strip()
        if not value or depth > 8:
            return ""
        if value.startswith("@"):
            return resolve(values.get(value[1:], ""), depth + 1)
        return value

    bg = resolve(values.get("bg")) or "#1e1e2e"
    fg = resolve(values.get("fg")) or meta.get("CAL_DAY", "#ffffff")
    accent = resolve(values.get("accent")) or meta.get("CAL_TODAY_BG", "#7aa2f7")
    accent_hi = (
        resolve(values.get("accent-hi"))
        or resolve(values.get("border-col"))
        or accent
    )
    return [bg, fg, accent, accent_hi]


def parse_color(value):
    value = (value or "").strip()
    named = {
        "white": (1.0, 1.0, 1.0, 1.0),
        "black": (0.0, 0.0, 0.0, 1.0),
        "gray": (0.5, 0.5, 0.5, 1.0),
        "grey": (0.5, 0.5, 0.5, 1.0),
    }
    if value.casefold() in named:
        return named[value.casefold()]
    if value.startswith("#"):
        digits = value[1:]
        if len(digits) in (3, 4):
            digits = "".join(char * 2 for char in digits)
        if len(digits) == 6:
            digits += "ff"
        if len(digits) == 8:
            try:
                return tuple(int(digits[index:index + 2], 16) / 255 for index in (0, 2, 4, 6))
            except ValueError:
                pass
    match = re.match(r"rgba?\(([^)]+)\)", value)
    if match:
        parts = [part.strip() for part in match.group(1).split(",")]
        if len(parts) >= 3:
            try:
                channels = []
                for part in parts[:3]:
                    if part.endswith("%"):
                        channels.append(max(0.0, min(1.0, float(part[:-1]) / 100)))
                    else:
                        channels.append(max(0.0, min(1.0, float(part) / 255)))
                alpha = float(parts[3]) if len(parts) > 3 else 1.0
                return (*channels, max(0.0, min(1.0, alpha)))
            except ValueError:
                pass
    return (0.5, 0.5, 0.5, 1.0)


def gtk_theme_palette(path):
    slug = path.name.casefold()
    dark = any(token in slug for token in ("dark", "nokto", "night", "black"))
    if "nord" in slug:
        fallback_accent = "#88c0d0"
    elif "dracula" in slug:
        fallback_accent = "#bd93f9"
    elif "materia" in slug:
        fallback_accent = "#8ab4f8"
    elif "orchis" in slug:
        fallback_accent = "#3281ea"
    elif "breeze" in slug:
        fallback_accent = "#3daee9"
    elif "adapta" in slug:
        fallback_accent = "#00bcd4"
    elif "adwaita" in slug:
        fallback_accent = "#3584e4"
    else:
        fallback_accent = "#7aa2f7" if dark else "#3584e4"
    fallback_bg = "#1e1e2e" if dark else "#f5f5f5"
    fallback_fg = "#cdd6f4" if dark else "#2e3436"
    fallback_hi = "#11111b" if dark else "#ffffff"

    text = ""
    for relative in ("gtk-3.0/gtk-dark.css", "gtk-3.0/gtk.css", "gtk-4.0/gtk-dark.css", "gtk-4.0/gtk.css"):
        source = path / relative
        if not source.is_file():
            continue
        try:
            candidate = source.read_text(encoding="utf-8")
        except OSError:
            continue
        if "@define-color" in candidate:
            text = candidate
            break

    definitions = {}
    for match in re.finditer(r"@define-color\s+([A-Za-z0-9_-]+)\s+([^;]+);", text):
        definitions[match.group(1)] = match.group(2).strip()

    def resolve(value, depth=0):
        value = (value or "").strip()
        if not value or depth > 8:
            return ""
        if value.startswith("@"):
            return resolve(definitions.get(value[1:], ""), depth + 1)
        return value

    def lookup(*keys):
        for key in keys:
            if key in definitions:
                return resolve(definitions[key])
        for defined, value in definitions.items():
            for key in keys:
                if key in defined:
                    return resolve(value)
        return ""

    bg = lookup("theme_bg_color", "bg_color", "theme_base_color") or fallback_bg
    fg = lookup("theme_fg_color", "fg_color", "theme_text_color") or fallback_fg
    accent = lookup("theme_selected_bg_color", "accent_color", "purple", "blue_3") or fallback_accent
    accent_hi = lookup("theme_selected_fg_color", "accent_fg_color") or fallback_hi
    return [bg, fg, accent, accent_hi]


def gtk_theme_name(path):
    index = path / "index.theme"
    if index.is_file():
        try:
            name = read_meta(index).get("Name", "")
        except OSError:
            name = ""
        if name and name != path.name:
            return name
    return path.name.replace("-", " ").replace("_", " ").title()


def load_gtk_themes():
    themes = []
    seen = set()
    for base in GTK_THEME_DIRS:
        if not base.is_dir():
            continue
        try:
            entries = sorted(base.iterdir(), key=lambda item: item.name.casefold())
        except OSError:
            continue
        for path in entries:
            if not path.is_dir():
                continue
            slug = path.name
            folded = slug.casefold()
            if folded.startswith("catppuccin-mocha"):
                continue
            if any(folded.endswith(suffix) for suffix in GTK_SKIP_SUFFIXES):
                continue
            if slug in seen:
                continue
            if not ((path / "gtk-3.0").is_dir() or (path / "gtk-4.0").is_dir()):
                continue
            seen.add(slug)
            themes.append(
                {
                    "slug": slug,
                    "name": gtk_theme_name(path),
                    "colors": gtk_theme_palette(path),
                    "gtk4": (path / "gtk-4.0").is_dir(),
                }
            )
    return sorted(themes, key=lambda theme: theme["name"].casefold())


def load_icon_themes():
    themes = {}
    for base in ICON_THEME_DIRS:
        if not base.is_dir():
            continue
        try:
            entries = sorted(base.iterdir(), key=lambda item: item.name.casefold())
        except OSError:
            continue
        for path in entries:
            if not path.is_dir():
                continue
            if not (path / "index.theme").is_file():
                continue
            slug = path.name
            if slug in themes:
                continue
            try:
                name = read_meta(path / "index.theme").get("Name", slug)
            except OSError:
                name = slug
            themes[slug] = name or slug
    current = gsetting("icon-theme")
    if current and current not in themes:
        themes[current] = f"{current} (current)"
    return sorted(themes.items(), key=lambda item: item[1].casefold())


def load_themes():
    themes = []
    for path in THEMES_DIR.iterdir():
        if path.is_symlink() or not path.is_dir():
            continue
        meta_path = path / "meta.conf"
        if not meta_path.is_file():
            continue
        meta = read_meta(meta_path)
        themes.append(
            {
                "slug": path.name,
                "name": meta.get("NAME", path.name.replace("-", " ").title()),
                "meta": meta,
                "colors": theme_palette(path, meta),
            }
        )
    return sorted(themes, key=lambda theme: theme["name"].casefold())


def current_theme_slug():
    link = THEMES_DIR / "current"
    if not link.is_symlink():
        return ""
    try:
        return Path(os.readlink(link)).name
    except OSError:
        return ""


def focus_enabled():
    try:
        return FOCUS_STATE.read_text(encoding="utf-8").strip() == "on"
    except OSError:
        return False


def waybar_state():
    fallback = {
        "bar_color": "#282a36",
        "bar_opacity": 0.35,
        "pill_color": "#44475a",
        "pill_opacity": 0.55,
        "text_color": "#f8f8f2",
        "bar_radius": 18,
        "pill_radius": 9,
        "text_align": "default",
    }
    try:
        result = subprocess.run(
            ["python3", str(WAYBAR_STYLE_SCRIPT), "print"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if isinstance(data, dict):
                fallback.update(data)
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return fallback


def read_waybar_settings():
    try:
        data = json.loads(WAYBAR_SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_waybar_settings(settings):
    WAYBAR_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    WAYBAR_SETTINGS_FILE.write_text(
        json.dumps(settings, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_waybar_style(command):
    try:
        subprocess.run(
            ["python3", str(WAYBAR_STYLE_SCRIPT), command, "--quiet"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def gsetting(key):
    try:
        result = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", key],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    value = result.stdout.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value


def gtk_ini(key):
    path = HOME / ".config" / "gtk-3.0" / "settings.ini"
    if not path.is_file():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


class SettingsWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Appearance")
        self.set_default_size(980, 700)
        self.toast_overlay = Adw.ToastOverlay()
        self.stack = Adw.ViewStack()
        self._theme_names = {}
        self._theme_badges = {}
        self._wallpaper_cards = []
        self._wallpaper_badges = {}
        self._wallpaper_loaded = False
        self._focus_guard = False
        self._applying = False
        self._system_rows = {}
        self._waybar_guard = False
        self._waybar_timeout = 0
        self._waybar_pending = {}
        self._gtk_names = {}
        self._gtk_badges = {}
        self._gtk_applying = False
        self._build_ui()
        self._refresh_theme_current()
        self._refresh_system_info()
        self._refresh_gtk_current()
        GLib.timeout_add_seconds(1, self._poll_focus)

    def _build_ui(self):
        header = Adw.HeaderBar()
        switcher = Adw.ViewSwitcher()
        switcher.set_stack(self.stack)
        switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)
        header.set_title_widget(switcher)

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header)
        toolbar.set_content(self.stack)

        self.toast_overlay.set_child(toolbar)
        self.set_content(self.toast_overlay)

        self.stack.add_titled(self._build_themes_page(), "themes", "Themes")
        self.stack.add_titled(self._build_gtk_page(), "gtk", "GTK")
        self.stack.add_titled(self._build_wallpaper_page(), "wallpapers", "Wallpaper")
        self.stack.add_titled(self._build_waybar_page(), "waybar", "Waybar")
        self.stack.add_titled(self._build_system_page(), "system", "System")

        initial_page = os.environ.get("RICE_SETTINGS_PAGE", "")
        if initial_page in ("themes", "gtk", "wallpapers", "waybar", "system"):
            self.stack.set_visible_child_name(initial_page)

    def _build_themes_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page.set_margin_top(18)
        page.set_margin_bottom(18)
        page.set_margin_start(18)
        page.set_margin_end(18)

        self.theme_search = Gtk.SearchEntry()
        self.theme_search.set_placeholder_text("Search themes")
        self.theme_search.connect("search-changed", self._on_theme_search)
        page.append(self.theme_search)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.theme_flow = Gtk.FlowBox()
        self.theme_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.theme_flow.set_homogeneous(True)
        self.theme_flow.set_column_spacing(12)
        self.theme_flow.set_row_spacing(12)
        self.theme_flow.set_max_children_per_line(3)
        self.theme_flow.set_min_children_per_line(1)
        self.theme_flow.set_filter_func(self._filter_theme)
        scroll.set_child(self.theme_flow)
        page.append(scroll)

        for theme in load_themes():
            self._add_theme_card(theme)
        return page

    def _add_theme_card(self, theme):
        button = Gtk.Button()
        button.add_css_class("card")
        button.set_size_request(250, -1)
        button.set_tooltip_text(f"Apply {theme['name']}")

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.set_margin_top(14)
        content.set_margin_bottom(14)
        content.set_margin_start(14)
        content.set_margin_end(14)

        swatches = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for color in theme["colors"]:
            area = Gtk.DrawingArea()
            area.set_size_request(26, 26)
            area.set_tooltip_text(color)
            area.set_draw_func(self._draw_swatch, color)
            swatches.append(area)
        content.append(swatches)

        line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        name = Gtk.Label(label=theme["name"], xalign=0)
        name.add_css_class("title-4")
        name.set_hexpand(True)
        name.set_ellipsize(Pango.EllipsizeMode.END)
        badge = Gtk.Label(label="Current")
        badge.add_css_class("accent")
        badge.add_css_class("caption")
        badge.set_visible(False)
        line.append(name)
        line.append(badge)
        content.append(line)

        button.set_child(content)
        button.connect("clicked", self._on_theme_clicked, theme)
        self.theme_flow.append(button)
        self._theme_names[button] = f"{theme['name']} {theme['slug']}"
        self._theme_badges[theme["slug"]] = badge

    def _draw_swatch(self, _area, cr, width, height, color):
        red, green, blue, alpha = parse_color(color)
        cr.set_source_rgba(red, green, blue, alpha)
        cr.arc(width / 2, height / 2, max(1, min(width, height) / 2 - 1), 0, 2 * math.pi)
        cr.fill()

    def _on_theme_search(self, _entry):
        self.theme_flow.invalidate_filter()

    def _filter_theme(self, child):
        query = self.theme_search.get_text().strip().casefold()
        if not query:
            return True
        widget = child.get_child() if isinstance(child, Gtk.FlowBoxChild) else child
        return query in self._theme_names.get(widget, "").casefold()

    def _on_theme_clicked(self, _button, theme):
        self._apply_theme(theme["slug"], theme["name"])

    def _refresh_theme_current(self):
        current = current_theme_slug()
        for slug, badge in self._theme_badges.items():
            badge.set_visible(slug == current)

    def _build_gtk_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page.set_margin_top(18)
        page.set_margin_bottom(18)
        page.set_margin_start(18)
        page.set_margin_end(18)

        icon_group = Adw.PreferencesGroup(
            title="Icons",
            description="Applied together with the selected GTK theme",
        )
        self.gtk_icon_combo = Adw.ComboRow(title="Icon theme")
        icon_themes = load_icon_themes()
        self._icon_slugs = [slug for slug, _name in icon_themes]
        labels = [name for _slug, name in icon_themes]
        if not labels:
            labels = ["No icon themes found"]
            self._icon_slugs = [""]
        self.gtk_icon_combo.set_model(Gtk.StringList.new(labels))
        icon_group.add(self.gtk_icon_combo)

        icon_row = Adw.ActionRow(
            title="Apply icon theme",
            subtitle="Change icons without changing GTK or the rice",
        )
        icon_button = Gtk.Button(label="Apply")
        icon_button.add_css_class("flat")
        icon_button.set_valign(Gtk.Align.CENTER)
        icon_button.connect("clicked", self._apply_icon_clicked)
        icon_row.add_suffix(icon_button)
        icon_group.add(icon_row)
        page.append(icon_group)

        self.gtk_status = Gtk.Label(label="Current GTK theme: unknown", xalign=0)
        self.gtk_status.add_css_class("dim-label")
        page.append(self.gtk_status)

        self.gtk_search = Gtk.SearchEntry()
        self.gtk_search.set_placeholder_text("Search GTK themes")
        self.gtk_search.connect("search-changed", self._on_gtk_search)
        page.append(self.gtk_search)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.gtk_flow = Gtk.FlowBox()
        self.gtk_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.gtk_flow.set_homogeneous(True)
        self.gtk_flow.set_column_spacing(12)
        self.gtk_flow.set_row_spacing(12)
        self.gtk_flow.set_max_children_per_line(3)
        self.gtk_flow.set_min_children_per_line(1)
        self.gtk_flow.set_filter_func(self._filter_gtk)
        scroll.set_child(self.gtk_flow)
        page.append(scroll)

        for theme in load_gtk_themes():
            self._add_gtk_card(theme)
        self._refresh_icon_choice()
        return page

    def _add_gtk_card(self, theme):
        button = Gtk.Button()
        button.add_css_class("card")
        button.set_size_request(250, -1)
        button.set_tooltip_text(f"Apply {theme['name']} (GTK and icons only)")

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.set_margin_top(14)
        content.set_margin_bottom(14)
        content.set_margin_start(14)
        content.set_margin_end(14)

        swatches = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for color in theme["colors"]:
            area = Gtk.DrawingArea()
            area.set_size_request(26, 26)
            area.set_tooltip_text(color)
            area.set_draw_func(self._draw_swatch, color)
            swatches.append(area)
        content.append(swatches)

        line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        name = Gtk.Label(label=theme["name"], xalign=0)
        name.add_css_class("title-4")
        name.set_hexpand(True)
        name.set_ellipsize(Pango.EllipsizeMode.END)
        if not theme["gtk4"]:
            gtk3 = Gtk.Label(label="GTK3")
            gtk3.add_css_class("caption")
            gtk3.add_css_class("dim-label")
            line.append(gtk3)
        badge = Gtk.Label(label="Current")
        badge.add_css_class("accent")
        badge.add_css_class("caption")
        badge.set_visible(False)
        line.append(name)
        line.append(badge)
        content.append(line)

        button.set_child(content)
        button.connect("clicked", self._on_gtk_clicked, theme)
        self.gtk_flow.append(button)
        self._gtk_names[button] = f"{theme['name']} {theme['slug']}"
        self._gtk_badges[theme["slug"]] = badge

    def _on_gtk_search(self, _entry):
        self.gtk_flow.invalidate_filter()

    def _filter_gtk(self, child):
        query = self.gtk_search.get_text().strip().casefold()
        if not query:
            return True
        widget = child.get_child() if isinstance(child, Gtk.FlowBoxChild) else child
        return query in self._gtk_names.get(widget, "").casefold()

    def _on_gtk_clicked(self, _button, theme):
        self._apply_gtk_theme(theme["slug"], theme["name"])

    def _selected_icon(self):
        index = self.gtk_icon_combo.get_selected()
        if 0 <= index < len(self._icon_slugs):
            return self._icon_slugs[index]
        return ""

    def _apply_gtk_theme(self, slug, name):
        if self._gtk_applying:
            return
        self._gtk_applying = True
        self._toast(f"Applying {name}…")
        threading.Thread(
            target=self._apply_gtk_worker,
            args=(slug, name, self._selected_icon()),
            daemon=True,
        ).start()

    def _apply_gtk_worker(self, slug, name, icon):
        try:
            result = subprocess.run(
                ["bash", str(GTK_THEME_SCRIPT), "apply", slug, icon],
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = (result.stderr or result.stdout or "").strip()
            GLib.idle_add(self._apply_gtk_done, name, result.returncode, output)
        except (OSError, subprocess.SubprocessError) as error:
            GLib.idle_add(self._apply_gtk_done, name, 1, str(error))

    def _apply_gtk_done(self, name, returncode, output):
        self._gtk_applying = False
        if returncode != 0:
            self._show_error("GTK theme could not be applied", output)
            return False
        self._refresh_system_info()
        self._refresh_gtk_current()
        self._refresh_icon_choice()
        self._toast(f"{name} GTK theme applied")
        return False

    def _apply_icon_clicked(self, _button):
        icon = self._selected_icon()
        if not icon:
            self._toast("No icon theme selected")
            return
        if self._gtk_applying:
            return
        self._gtk_applying = True
        self._toast(f"Applying {icon}…")
        threading.Thread(
            target=self._apply_icon_worker,
            args=(icon,),
            daemon=True,
        ).start()

    def _apply_icon_worker(self, icon):
        try:
            result = subprocess.run(
                ["bash", str(GTK_THEME_SCRIPT), "icon", icon],
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = (result.stderr or result.stdout or "").strip()
            GLib.idle_add(self._apply_icon_done, icon, result.returncode, output)
        except (OSError, subprocess.SubprocessError) as error:
            GLib.idle_add(self._apply_icon_done, icon, 1, str(error))

    def _apply_icon_done(self, icon, returncode, output):
        self._gtk_applying = False
        if returncode != 0:
            self._show_error("Icon theme could not be applied", output)
            return False
        self._refresh_system_info()
        self._refresh_icon_choice()
        self._toast(f"{icon} applied")
        return False

    def _refresh_gtk_current(self):
        current = gsetting("gtk-theme")
        if hasattr(self, "gtk_status"):
            self.gtk_status.set_text(f"Current GTK theme: {current or 'Unknown'}")
        for slug, badge in self._gtk_badges.items():
            badge.set_visible(slug == current)

    def _refresh_icon_choice(self):
        if not hasattr(self, "gtk_icon_combo"):
            return
        current = gsetting("icon-theme")
        if current in self._icon_slugs:
            self.gtk_icon_combo.set_selected(self._icon_slugs.index(current))
            self.gtk_icon_combo.set_tooltip_text(current)

    def _show_gtk_page(self):
        self.stack.set_visible_child_name("gtk")

    def _apply_theme(self, slug, name):
        if self._applying:
            return
        self._applying = True
        self._toast(f"Applying {name}…")
        threading.Thread(target=self._apply_theme_worker, args=(slug, name), daemon=True).start()

    def _apply_theme_worker(self, slug, name):
        try:
            result = subprocess.run(
                ["bash", str(THEMES_DIR / "apply.sh"), slug],
                capture_output=True,
                text=True,
                timeout=60,
            )
            output = (result.stderr or result.stdout or "").strip()
            GLib.idle_add(self._apply_theme_done, name, result.returncode, output)
        except (OSError, subprocess.SubprocessError) as error:
            GLib.idle_add(self._apply_theme_done, name, 1, str(error))

    def _apply_theme_done(self, name, returncode, output):
        self._applying = False
        if returncode != 0:
            self._show_error("Theme could not be applied", output)
            return False
        self._refresh_theme_current()
        self._refresh_system_info()
        self._refresh_waybar_controls()
        self._refresh_gtk_current()
        self._refresh_icon_choice()
        self._toast(f"{name} applied")
        return False

    def _build_wallpaper_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page.set_margin_top(18)
        page.set_margin_bottom(18)
        page.set_margin_start(18)
        page.set_margin_end(18)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.wallpaper_status = Gtk.Label(label="Loading wallpapers…", xalign=0)
        self.wallpaper_status.add_css_class("dim-label")
        self.wallpaper_status.set_hexpand(True)
        actions.append(self.wallpaper_status)

        for label, callback in (
            ("Random", lambda _button: self._wallpaper_action("--random")),
            ("Next", lambda _button: self._wallpaper_action("--next")),
            ("Refresh", lambda _button: self._load_wallpapers()),
            ("Open Folder", lambda _button: self._open_folder(WALLPAPER_DIR)),
        ):
            button = Gtk.Button(label=label)
            button.add_css_class("flat")
            button.connect("clicked", callback)
            actions.append(button)
        page.append(actions)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.wallpaper_flow = Gtk.FlowBox()
        self.wallpaper_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.wallpaper_flow.set_homogeneous(True)
        self.wallpaper_flow.set_column_spacing(12)
        self.wallpaper_flow.set_row_spacing(12)
        self.wallpaper_flow.set_max_children_per_line(3)
        self.wallpaper_flow.set_min_children_per_line(1)
        scroll.set_child(self.wallpaper_flow)
        page.append(scroll)

        self._load_wallpapers()
        return page

    def _load_wallpapers(self):
        self.wallpaper_status.set_text("Loading wallpapers…")
        threading.Thread(target=self._load_wallpapers_worker, daemon=True).start()

    def _load_wallpapers_worker(self):
        try:
            result = subprocess.run(
                ["bash", str(WALLPAPER_SCRIPT), "--list"],
                capture_output=True,
                text=True,
                timeout=20,
            )
            relative_paths = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        except (OSError, subprocess.SubprocessError):
            relative_paths = []

        try:
            current = subprocess.run(
                ["bash", str(WALLPAPER_SCRIPT), "--current"],
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            current = ""

        entries = []
        for relative in relative_paths:
            source = WALLPAPER_DIR / relative
            if source.is_file():
                entries.append((relative, source, self._thumbnail(source)))
        GLib.idle_add(self._populate_wallpapers, entries, current)
        return False

    def _thumbnail(self, source):
        try:
            THUMB_DIR.mkdir(parents=True, exist_ok=True)
            key = hashlib.md5(str(source).encode("utf-8")).hexdigest()
            thumb = THUMB_DIR / f"{key}.png"
            if thumb.is_file() and thumb.stat().st_mtime >= source.stat().st_mtime:
                return thumb
            if shutil.which("magick"):
                subprocess.run(
                    [
                        "magick",
                        f"{source}[0]",
                        "-thumbnail",
                        "480x270^",
                        "-gravity",
                        "center",
                        "-extent",
                        "480x270",
                        str(thumb),
                    ],
                    capture_output=True,
                    timeout=20,
                )
                if thumb.is_file():
                    return thumb
        except (OSError, subprocess.SubprocessError):
            pass
        return source

    def _populate_wallpapers(self, entries, current):
        for card in self._wallpaper_cards:
            self.wallpaper_flow.remove(card)
        self._wallpaper_cards.clear()
        self._wallpaper_badges.clear()

        if not entries:
            self.wallpaper_status.set_text(f"No wallpapers found in {WALLPAPER_DIR}")
            self._wallpaper_loaded = True
            return False

        self.wallpaper_status.set_text(f"{len(entries)} wallpapers")
        current_path = Path(current).resolve() if current else None
        for relative, source, thumb in entries:
            button = Gtk.Button()
            button.add_css_class("card")
            button.set_size_request(240, -1)
            button.set_tooltip_text(f"Apply {relative}")

            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            content.set_margin_top(10)
            content.set_margin_bottom(10)
            content.set_margin_start(10)
            content.set_margin_end(10)

            picture = Gtk.Picture.new_for_filename(str(thumb))
            picture.set_content_fit(Gtk.ContentFit.COVER)
            picture.set_can_shrink(True)
            picture.set_size_request(220, 124)
            content.append(picture)

            line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            label = Gtk.Label(label=relative, xalign=0)
            label.set_hexpand(True)
            label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            label.set_tooltip_text(relative)
            badge = Gtk.Label(label="Current")
            badge.add_css_class("accent")
            badge.add_css_class("caption")
            badge.set_visible(current_path == source.resolve())
            line.append(label)
            line.append(badge)
            content.append(line)

            button.set_child(content)
            button.connect("clicked", self._apply_wallpaper, source)
            self.wallpaper_flow.append(button)
            self._wallpaper_cards.append(button)
            self._wallpaper_badges[str(source)] = badge

        self._wallpaper_loaded = True
        return False

    def _apply_wallpaper(self, _button, source):
        self._toast(f"Applying {source.name}…")
        threading.Thread(target=self._apply_wallpaper_worker, args=(source,), daemon=True).start()

    def _apply_wallpaper_worker(self, source):
        try:
            result = subprocess.run(
                ["bash", str(WALLPAPER_SCRIPT), str(source)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            output = (result.stderr or result.stdout or "").strip()
            GLib.idle_add(self._wallpaper_done, source.name, result.returncode, output)
        except (OSError, subprocess.SubprocessError) as error:
            GLib.idle_add(self._wallpaper_done, source.name, 1, str(error))

    def _wallpaper_done(self, name, returncode, output):
        if returncode != 0:
            self._show_error("Wallpaper could not be applied", output)
            return False
        self._refresh_wallpaper_current()
        self._toast(f"{name} applied")
        return False

    def _wallpaper_action(self, flag):
        threading.Thread(target=self._wallpaper_action_worker, args=(flag,), daemon=True).start()

    def _wallpaper_action_worker(self, flag):
        try:
            result = subprocess.run(
                ["bash", str(WALLPAPER_SCRIPT), flag],
                capture_output=True,
                text=True,
                timeout=60,
            )
            output = (result.stderr or result.stdout or "").strip()
            GLib.idle_add(self._wallpaper_action_done, flag, result.returncode, output)
        except (OSError, subprocess.SubprocessError) as error:
            GLib.idle_add(self._wallpaper_action_done, flag, 1, str(error))

    def _wallpaper_action_done(self, flag, returncode, output):
        if returncode != 0:
            self._show_error("Wallpaper action failed", output)
            return False
        self._refresh_wallpaper_current()
        self._toast("Wallpaper changed")
        return False

    def _refresh_wallpaper_current(self):
        try:
            current = subprocess.run(
                ["bash", str(WALLPAPER_SCRIPT), "--current"],
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            current = ""
        current_path = Path(current).resolve() if current else None
        for path, badge in self._wallpaper_badges.items():
            badge.set_visible(current_path == Path(path).resolve())

    def _build_waybar_page(self):
        page = Adw.PreferencesPage()
        state = waybar_state()
        self._waybar_guard = True
        self.waybar_color_dialog = Gtk.ColorDialog()
        self.waybar_color_dialog.set_with_alpha(False)

        bar_group = Adw.PreferencesGroup(
            title="Bar",
            description="Background and shape of the main bar",
        )
        self.waybar_bar_color = self._add_waybar_color(
            bar_group,
            "Background color",
            "Base color behind the bar",
            "bar_color",
            state,
        )
        self.waybar_bar_opacity = self._add_waybar_scale(
            bar_group,
            "Transparency",
            "Lower values make the bar more transparent",
            0,
            100,
            round(float(state.get("bar_opacity", 0.35)) * 100),
            "bar_opacity",
        )
        self.waybar_bar_radius = self._add_waybar_scale(
            bar_group,
            "Corner radius",
            "Rounded corners at the bottom of the bar",
            0,
            40,
            int(state.get("bar_radius", 18)),
            "bar_radius",
        )
        page.add(bar_group)

        pill_group = Adw.PreferencesGroup(
            title="Module Pills",
            description="Colors and shape of the module backgrounds",
        )
        self.waybar_pill_color = self._add_waybar_color(
            pill_group,
            "Pill background",
            "Background color for modules and the tray",
            "pill_color",
            state,
        )
        self.waybar_pill_opacity = self._add_waybar_scale(
            pill_group,
            "Pill transparency",
            "Lower values make module backgrounds more transparent",
            0,
            100,
            round(float(state.get("pill_opacity", 0.55)) * 100),
            "pill_opacity",
        )
        self.waybar_pill_radius = self._add_waybar_scale(
            pill_group,
            "Pill corner radius",
            "Rounded corners on module backgrounds",
            0,
            30,
            int(state.get("pill_radius", 9)),
            "pill_radius",
        )
        self.waybar_text_color = self._add_waybar_color(
            pill_group,
            "Text color",
            "Text and icon color inside modules",
            "text_color",
            state,
        )
        page.add(pill_group)

        layout_group = Adw.PreferencesGroup(title="Layout")
        self.waybar_align = Adw.ComboRow(
            title="Text alignment",
            subtitle="Justify text inside label modules",
        )
        self.waybar_align.set_model(
            Gtk.StringList.new(["Theme default", "Left", "Center", "Right"])
        )
        self.waybar_align.set_selected(
            {"default": 0, "left": 1, "center": 2, "right": 3}.get(
                state.get("text_align", "default"), 0
            )
        )
        self.waybar_align.connect("notify::selected", self._on_waybar_align)
        layout_group.add(self.waybar_align)
        page.add(layout_group)

        actions = Adw.PreferencesGroup(title="Actions")
        for title, subtitle, label, callback in (
            ("Reload Waybar", "Restart the bar and reload its config", "Reload", self._reload_waybar),
            ("Reset appearance", "Return to the current theme's Waybar styling", "Reset", self._reset_waybar),
            ("Waybar Folder", "Browse Waybar configuration and scripts", "Open", lambda: self._open_folder(LIVE_WAYBAR_DIR)),
        ):
            row = Adw.ActionRow(title=title, subtitle=subtitle)
            button = Gtk.Button(label=label)
            button.add_css_class("flat")
            button.set_valign(Gtk.Align.CENTER)
            button.connect("clicked", lambda _button, handler=callback: handler())
            row.add_suffix(button)
            actions.add(row)
        page.add(actions)

        self._waybar_guard = False
        return page

    def _add_waybar_color(self, group, title, subtitle, key, state):
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        button = Gtk.ColorDialogButton()
        button.set_dialog(self.waybar_color_dialog)
        button.set_rgba(self._rgba_from_hex(state.get(key, "#000000")))
        button.set_valign(Gtk.Align.CENTER)
        button.set_tooltip_text(title)
        button.connect("notify::rgba", self._on_waybar_color, key)
        row.add_suffix(button)
        group.add(row)
        return button

    def _add_waybar_scale(self, group, title, subtitle, minimum, maximum, value, key):
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL,
            minimum,
            maximum,
            1,
        )
        scale.set_size_request(210, -1)
        scale.set_draw_value(True)
        scale.set_value_pos(Gtk.PositionType.RIGHT)
        scale.set_digits(0)
        scale.set_value(value)
        scale.set_valign(Gtk.Align.CENTER)
        scale.connect("value-changed", self._on_waybar_scale, key)
        row.add_suffix(scale)
        group.add(row)
        return scale

    def _rgba_from_hex(self, value):
        red, green, blue, alpha = parse_color(value)
        rgba = Gdk.RGBA()
        rgba.red = red
        rgba.green = green
        rgba.blue = blue
        rgba.alpha = alpha
        return rgba

    def _hex_from_rgba(self, rgba):
        def channel(value):
            return round(max(0.0, min(1.0, value)) * 255)

        return "#{:02x}{:02x}{:02x}".format(
            channel(rgba.red),
            channel(rgba.green),
            channel(rgba.blue),
        )

    def _on_waybar_color(self, button, _pspec, key):
        if self._waybar_guard:
            return
        self._queue_waybar_setting(key, self._hex_from_rgba(button.get_rgba()))

    def _on_waybar_scale(self, scale, key):
        if self._waybar_guard:
            return
        value = scale.get_value()
        if key.endswith("_opacity"):
            value = value / 100.0
        else:
            value = int(round(value))
        self._queue_waybar_setting(key, value)

    def _on_waybar_align(self, combo, _pspec):
        if self._waybar_guard:
            return
        values = ("default", "left", "center", "right")
        index = combo.get_selected()
        value = values[index] if 0 <= index < len(values) else "default"
        self._queue_waybar_setting("text_align", value)

    def _queue_waybar_setting(self, key, value):
        if self._waybar_guard:
            return
        self._waybar_pending[key] = value
        if self._waybar_timeout:
            GLib.source_remove(self._waybar_timeout)
        self._waybar_timeout = GLib.timeout_add(180, self._flush_waybar_pending)

    def _flush_waybar_pending(self):
        self._waybar_timeout = 0
        pending = self._waybar_pending
        self._waybar_pending = {}
        if not pending:
            return False
        settings = read_waybar_settings()
        settings.update(pending)
        write_waybar_settings(settings)
        if not run_waybar_style("apply"):
            self._toast("Could not update Waybar")
            self._refresh_waybar_controls()
        return False

    def _refresh_waybar_controls(self):
        state = waybar_state()
        self._waybar_guard = True
        try:
            self.waybar_bar_color.set_rgba(self._rgba_from_hex(state.get("bar_color", "#282a36")))
            self.waybar_bar_opacity.set_value(round(float(state.get("bar_opacity", 0.35)) * 100))
            self.waybar_bar_radius.set_value(int(state.get("bar_radius", 18)))
            self.waybar_pill_color.set_rgba(self._rgba_from_hex(state.get("pill_color", "#44475a")))
            self.waybar_pill_opacity.set_value(round(float(state.get("pill_opacity", 0.55)) * 100))
            self.waybar_pill_radius.set_value(int(state.get("pill_radius", 9)))
            self.waybar_text_color.set_rgba(self._rgba_from_hex(state.get("text_color", "#f8f8f2")))
            self.waybar_align.set_selected(
                {"default": 0, "left": 1, "center": 2, "right": 3}.get(
                    state.get("text_align", "default"), 0
                )
            )
        finally:
            self._waybar_guard = False

    def _reset_waybar(self):
        if not run_waybar_style("reset"):
            self._toast("Could not reset Waybar appearance")
            return
        self._refresh_waybar_controls()
        self._toast("Waybar appearance reset")

    def _reload_waybar(self):
        if not run_waybar_style("restart"):
            self._toast("Could not reload Waybar")
            return
        self._toast("Waybar reloaded")

    def _build_system_page(self):
        page = Adw.PreferencesPage()

        theme_group = Adw.PreferencesGroup(title="Desktop Theme")
        for key, title in (
            ("gtk", "GTK Theme"),
            ("icon", "Icon Theme"),
            ("cursor", "Cursor Theme"),
            ("font", "Font"),
        ):
            row = Adw.ActionRow(title=title)
            theme_group.add(row)
            self._system_rows[key] = row
        page.add(theme_group)

        bar_group = Adw.PreferencesGroup(title="Bar")
        self.focus_switch = Adw.SwitchRow(
            title="Focus Mode",
            subtitle="Show the compact workspace, tray, and mic notch",
        )
        self.focus_switch.set_active(focus_enabled())
        self.focus_switch.connect("notify::active", self._on_focus_toggled)
        bar_group.add(self.focus_switch)
        page.add(bar_group)

        actions = Adw.PreferencesGroup(title="Actions")
        for title, subtitle, callback in (
            ("GTK Themes", "Browse installed GTK and icon themes", self._show_gtk_page),
            ("GTK Settings", "Open nwg-look", self._open_gtk_settings),
            ("Themes Folder", "Browse installed themes", lambda: self._open_folder(THEMES_DIR)),
            ("Wallpapers Folder", "Browse wallpaper images", lambda: self._open_folder(WALLPAPER_DIR)),
        ):
            row = Adw.ActionRow(title=title, subtitle=subtitle)
            button = Gtk.Button(label="Open")
            button.add_css_class("flat")
            button.set_valign(Gtk.Align.CENTER)
            button.connect("clicked", lambda _button, handler=callback: handler())
            row.add_suffix(button)
            actions.add(row)
        page.add(actions)
        return page

    def _refresh_system_info(self):
        values = {
            "gtk": gsetting("gtk-theme") or gtk_ini("gtk-theme-name") or "Unknown",
            "icon": gsetting("icon-theme") or gtk_ini("gtk-icon-theme-name") or "Unknown",
            "cursor": gsetting("cursor-theme") or gtk_ini("gtk-cursor-theme-name") or "Unknown",
            "font": gsetting("font-name") or gtk_ini("gtk-font-name") or "Unknown",
        }
        for key, value in values.items():
            row = self._system_rows.get(key)
            if row is not None:
                row.set_subtitle(value)

    def _on_focus_toggled(self, _switch, _pspec):
        if self._focus_guard:
            return
        desired = "on" if self.focus_switch.get_active() else "off"
        if not FOCUS_SCRIPT.is_file():
            self._toast("Focus helper is not installed")
            self._set_focus_switch(not self.focus_switch.get_active())
            return
        try:
            subprocess.run(
                ["bash", str(FOCUS_SCRIPT), desired],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
        except (OSError, subprocess.SubprocessError):
            self._toast("Could not change focus mode")
            self._set_focus_switch(not self.focus_switch.get_active())

    def _set_focus_switch(self, enabled):
        self._focus_guard = True
        self.focus_switch.set_active(enabled)
        self._focus_guard = False

    def _poll_focus(self):
        enabled = focus_enabled()
        if self.focus_switch.get_active() != enabled:
            self._set_focus_switch(enabled)
        return True

    def _open_gtk_settings(self):
        if shutil.which("nwg-look"):
            subprocess.Popen(["nwg-look"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            self._toast("nwg-look is not installed")

    def _open_folder(self, path):
        if not path.is_dir():
            self._toast(f"Folder not found: {path}")
            return
        try:
            subprocess.Popen(
                ["xdg-open", str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            self._toast("Could not open folder")

    def _toast(self, message):
        toast = Adw.Toast.new(message)
        toast.set_timeout(2)
        self.toast_overlay.add_toast(toast)

    def _show_error(self, title, body):
        dialog = Adw.AlertDialog()
        dialog.set_heading(title)
        dialog.set_body((body or "Unknown error")[-1200:])
        dialog.add_response("close", "Close")
        dialog.present(self)


class SettingsApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="io.github.kishan362.NiriRice.Settings",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.window = None

    def do_activate(self):
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.PREFER_DARK)
        if self.window is None:
            self.window = SettingsWindow(application=self)
        self.window.present()


def main():
    app = SettingsApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
