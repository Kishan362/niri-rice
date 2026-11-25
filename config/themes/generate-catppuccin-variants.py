#!/usr/bin/env python3

import colorsys
import re
import sys
from pathlib import Path

THEMES_DIR = Path(__file__).resolve().parent
BASE_DIR = THEMES_DIR / "catppuccin-mocha"

PALETTE = {
    "rosewater": "#f5e0dc",
    "flamingo": "#f2cdcd",
    "pink": "#f5c2e7",
    "mauve": "#cba6f7",
    "red": "#f38ba8",
    "maroon": "#eba0ac",
    "peach": "#fab387",
    "yellow": "#f9e2af",
    "green": "#a6e3a1",
    "teal": "#94e2d5",
    "sky": "#89dceb",
    "sapphire": "#74c7ec",
    "blue": "#89b4fa",
    "lavender": "#b4befe",
}

VARIANTS = [
    ("rosewater", "Rosewater", "rosewater", "flamingo", "Tela-circle-pink-dark"),
    ("flamingo", "Flamingo", "flamingo", "rosewater", "Tela-circle-pink-dark"),
    ("pink", "Pink", "pink", "rosewater", "Tela-circle-pink-dark"),
    ("red", "Red", "red", "maroon", "Tela-circle-red-dark"),
    ("maroon", "Maroon", "maroon", "red", "Tela-circle-red-dark"),
    ("peach", "Peach", "peach", "yellow", "Tela-circle-orange-dark"),
    ("yellow", "Yellow", "yellow", "peach", "Tela-circle-yellow-dark"),
    ("green", "Green", "green", "teal", "Tela-circle-green-dark"),
    ("teal", "Teal", "teal", "green", "Tela-circle-blue-dark"),
    ("sky", "Sky", "sky", "sapphire", "Tela-circle-blue-dark"),
    ("sapphire", "Sapphire", "sapphire", "sky", "Tela-circle-blue-dark"),
    ("blue", "Blue", "blue", "lavender", "Tela-circle-blue-dark"),
    ("lavender", "Lavender", "lavender", "blue", "Tela-circle-purple-dark"),
]

BASE_FILES = (
    "waybar.css",
    "kitty.conf",
    "rofi.rasi",
    "niri.kdl",
    "mako.conf",
    "swaylock.conf",
    "zsh.sh",
)

BASE_ACCENT = "#cba6f7"
BASE_ACCENT_HI = "#f5c2e7"
BASE_ACCENT_DARK = "#7c5fbf"
BASE_TINT = "#2a2139"
BASE_HOVER = "#352c4a"
BASE_ICON = "Tela-circle-purple-dark"


def hex_to_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*(round(max(0, min(255, channel))) for channel in rgb))


def tone(accent, lightness, saturation):
    red, green, blue = hex_to_rgb(accent)
    hue, _, _ = colorsys.rgb_to_hls(red / 255, green / 255, blue / 255)
    red, green, blue = colorsys.hls_to_rgb(hue, lightness, saturation)
    return rgb_to_hex((red * 255, green * 255, blue * 255))


def replace_hash_colors(text, colors):
    names = "|".join(re.escape(name.lstrip("#")) for name in colors)
    pattern = re.compile(r"#(" + names + r")([0-9a-fA-F]{0,2})", re.I)
    return pattern.sub(
        lambda match: colors["#" + match.group(1).lower()] + match.group(2),
        text,
    )


def replace_bare_colors(text, colors):
    names = "|".join(re.escape(name.lstrip("#")) for name in colors)
    pattern = re.compile(
        r"(?<![#0-9a-fA-F])(" + names + r")([0-9a-fA-F]{0,2})(?![0-9a-fA-F])",
        re.I,
    )
    return pattern.sub(
        lambda match: colors["#" + match.group(1).lower()].lstrip("#") + match.group(2),
        text,
    )


def replace_rgba(text, rgb, new):
    red, green, blue = rgb
    new_red, new_green, new_blue = hex_to_rgb(new)
    return re.sub(
        rf"rgba\(\s*{red}\s*,\s*{green}\s*,\s*{blue}\s*,",
        f"rgba({new_red}, {new_green}, {new_blue},",
        text,
    )


def render_file(text, accent, accent_hi, accent_dark, tint, hover, icon):
    colors = {
        BASE_ACCENT: accent,
        BASE_ACCENT_HI: accent_hi,
        BASE_ACCENT_DARK: accent_dark,
        BASE_TINT: tint,
        BASE_HOVER: hover,
    }
    text = replace_hash_colors(text, colors)
    text = replace_bare_colors(text, colors)
    for old, new in (
        ((203, 166, 247), accent),
        ((42, 33, 57), tint),
        ((53, 44, 74), hover),
    ):
        text = replace_rgba(text, old, new)
    return text.replace(BASE_ICON, icon)


def render_variant(slug, title, accent_name, secondary_name, icon):
    accent = PALETTE[accent_name]
    accent_hi = PALETTE[secondary_name]
    accent_dark = tone(accent, 0.56, 0.42)
    tint = tone(accent, 0.18, 0.27)
    hover = tone(accent, 0.23, 0.26)

    files = {}
    for name in BASE_FILES:
        text = (BASE_DIR / name).read_text(encoding="utf-8")
        files[name] = render_file(text, accent, accent_hi, accent_dark, tint, hover, icon)

    files["meta.conf"] = "\n".join(
        [
            f'NAME="Catppuccin Mocha {title}"',
            f'GTK_THEME="catppuccin-mocha-{slug}-standard+default"',
            f'ICON_THEME="{icon}"',
            f'CAL_MONTH="{accent_hi}"',
            'CAL_DAY="#cdd6f4"',
            'CAL_WEEK="#6c7086"',
            f'CAL_WEEKDAY="{accent}"',
            'CAL_TODAY_FG="#11111b"',
            f'CAL_TODAY_BG="{accent}"',
            "",
        ]
    )
    return files


def main(argv):
    check = "--check" in argv[1:]
    changed = []

    for slug, title, accent_name, secondary_name, icon in VARIANTS:
        target = THEMES_DIR / f"catppuccin-mocha-{slug}"
        files = render_variant(slug, title, accent_name, secondary_name, icon)
        for name, text in files.items():
            path = target / name
            if check:
                if not path.is_file() or path.read_text(encoding="utf-8") != text:
                    changed.append(str(path))
            else:
                target.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")

    if check:
        if changed:
            print("Outdated Catppuccin variants:")
            for path in changed:
                print(f"  {path}")
            return 1
        print("Catppuccin variants are up to date")
        return 0

    print(f"Generated {len(VARIANTS)} Catppuccin variants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
