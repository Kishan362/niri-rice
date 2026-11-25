#!/usr/bin/env python3

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
WAYBAR = HOME / ".config" / "waybar"
THEMES = HOME / ".config" / "themes"
STYLE = WAYBAR / "style.css"
OVERRIDES = WAYBAR / "waybar-overrides.css"
SETTINGS = WAYBAR / "waybar-settings.json"
CONFIG = WAYBAR / "config.jsonc"
FOCUS = WAYBAR / "scripts" / "focus.sh"

MODULE_KEYS = [
    "custom/launcher",
    "niri/window",
    "mpris",
    "temperature",
    "cpu",
    "memory",
    "pulseaudio",
    "custom/microphone",
    "backlight",
    "custom/nightlight",
    "custom/caffeine",
    "battery",
    "clock",
    "custom/wallpaper",
    "custom/theme",
    "custom/power",
]

PILL_SELECTORS = """#custom-launcher,
#window,
#mpris,
#temperature,
#cpu,
#memory,
#pulseaudio,
#custom-microphone,
#backlight,
#custom-nightlight,
#custom-caffeine,
#battery,
#clock,
#tray,
#custom-wallpaper,
#custom-theme,
#custom-power"""

FALLBACK_THEME = {
    "bar_color": (40, 42, 54),
    "bar_opacity": 0.35,
    "pill_color": (68, 71, 90),
    "pill_opacity": 0.55,
    "text_color": (248, 248, 242),
    "bar_radius": 18,
    "pill_radius": 9,
}

VALID_ALIGNMENTS = {"default", "left", "center", "right"}


def clamp(value, low, high):
    return max(low, min(high, value))


def parse_color(value, fallback=None):
    value = (value or "").strip()
    if value.startswith("#"):
        digits = value[1:]
        if len(digits) in (3, 4):
            digits = "".join(char * 2 for char in digits)
        if len(digits) == 6:
            digits += "ff"
        if len(digits) == 8:
            try:
                return (
                    int(digits[0:2], 16),
                    int(digits[2:4], 16),
                    int(digits[4:6], 16),
                    int(digits[6:8], 16) / 255,
                )
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
                        channels.append(round(float(part[:-1]) * 2.55))
                    else:
                        channels.append(round(float(part)))
                alpha = 1.0
                if len(parts) > 3:
                    raw_alpha = parts[3]
                    if raw_alpha.endswith("%"):
                        alpha = float(raw_alpha[:-1]) / 100
                    else:
                        alpha = float(raw_alpha)
                return (
                    int(clamp(channels[0], 0, 255)),
                    int(clamp(channels[1], 0, 255)),
                    int(clamp(channels[2], 0, 255)),
                    clamp(alpha, 0.0, 1.0),
                )
            except ValueError:
                pass

    if value == "transparent":
        return (0, 0, 0, 0.0)
    return fallback


def hex_color(color):
    return "#{:02x}{:02x}{:02x}".format(*(int(clamp(channel, 0, 255)) for channel in color[:3]))


def rgba_css(color, alpha):
    red, green, blue = (int(clamp(channel, 0, 255)) for channel in color[:3])
    return f"rgba({red}, {green}, {blue}, {clamp(alpha, 0.0, 1.0):.2f})"


def get_prop(body, *names):
    for name in names:
        match = re.search(rf"(?:^|;)\s*{re.escape(name)}\s*:\s*([^;]+);", body)
        if match:
            return match.group(1).strip()
    return ""


def parse_radius(value, fallback):
    numbers = [float(number) for number in re.findall(r"(\d+(?:\.\d+)?)px", value or "")]
    return int(round(max(numbers))) if numbers else fallback


def css_blocks(css):
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css, re.S):
        yield " ".join(match.group(1).split()), match.group(2)


def theme_css_path():
    link = THEMES / "current"
    if link.is_symlink():
        try:
            target = Path(os.readlink(link))
        except OSError:
            target = None
        if target is not None:
            if not target.is_absolute():
                target = (link.parent / target).resolve()
            candidate = target / "waybar.css"
            if candidate.is_file():
                return candidate
    return STYLE


def theme_defaults():
    css = ""
    path = theme_css_path()
    if path.is_file():
        try:
            css = path.read_text(encoding="utf-8")
        except OSError:
            css = ""

    bar_body = ""
    pill_body = ""
    for selector, body in css_blocks(css):
        if selector == "window#waybar > box":
            bar_body = body
        elif "#custom-launcher" in selector and "#custom-power" in selector and "background" in body:
            pill_body = body

    bar = parse_color(get_prop(bar_body, "background", "background-color"), (*FALLBACK_THEME["bar_color"], FALLBACK_THEME["bar_opacity"]))
    pill = parse_color(get_prop(pill_body, "background", "background-color"), (*FALLBACK_THEME["pill_color"], FALLBACK_THEME["pill_opacity"]))
    text = parse_color(get_prop(pill_body, "color"), (*FALLBACK_THEME["text_color"], 1.0))

    return {
        "bar_color": bar[:3],
        "bar_opacity": bar[3],
        "pill_color": pill[:3],
        "pill_opacity": pill[3],
        "text_color": text[:3],
        "bar_radius": parse_radius(get_prop(bar_body, "border-radius"), FALLBACK_THEME["bar_radius"]),
        "pill_radius": parse_radius(get_prop(pill_body, "border-radius"), FALLBACK_THEME["pill_radius"]),
    }


def load_settings():
    if not SETTINGS.is_file():
        return {}
    try:
        data = json.loads(SETTINGS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(settings):
    if not settings:
        SETTINGS.unlink(missing_ok=True)
        return
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(settings, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def number(value, fallback, low, high):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return clamp(parsed, low, high)


def effective_state(theme, settings):
    bar_color = parse_color(settings.get("bar_color"), (*theme["bar_color"], 1.0))
    pill_color = parse_color(settings.get("pill_color"), (*theme["pill_color"], 1.0))
    text_color = parse_color(settings.get("text_color"), (*theme["text_color"], 1.0))
    alignment = settings.get("text_align", "default")
    if alignment not in VALID_ALIGNMENTS:
        alignment = "default"

    return {
        "bar_color": bar_color[:3],
        "bar_opacity": number(settings.get("bar_opacity"), theme["bar_opacity"], 0.0, 1.0),
        "pill_color": pill_color[:3],
        "pill_opacity": number(settings.get("pill_opacity"), theme["pill_opacity"], 0.0, 1.0),
        "text_color": text_color[:3],
        "bar_radius": int(number(settings.get("bar_radius"), theme["bar_radius"], 0, 40)),
        "pill_radius": int(number(settings.get("pill_radius"), theme["pill_radius"], 0, 30)),
        "text_align": alignment,
    }


def render_overrides(state, has_settings):
    if not has_settings:
        return "/* Generated by Appearance settings. */\n/* No custom Waybar appearance. */\n"

    return "\n".join(
        [
            "/* Generated by Appearance settings. */",
            "",
            "window#waybar > box {",
            f"    background: {rgba_css(state['bar_color'], state['bar_opacity'])};",
            f"    border-radius: 0 0 {state['bar_radius']}px {state['bar_radius']}px;",
            "}",
            "",
            "window#waybar.focus .modules-center {",
            f"    border-radius: 0 0 {state['bar_radius']}px {state['bar_radius']}px;",
            "}",
            "",
            PILL_SELECTORS + " {",
            f"    background: {rgba_css(state['pill_color'], state['pill_opacity'])};",
            f"    color: {hex_color(state['text_color'])};",
            f"    border-radius: {state['pill_radius']}px;",
            "}",
            "",
            "window#waybar.focus #tray,",
            "window#waybar.focus #custom-microphone {",
            "    background: transparent;",
            "    color: #ffffff;",
            "    border-radius: 0;",
            "}",
            "",
        ]
    )


def strip_overrides(text):
    text = re.sub(r'\n?@import url\(["\']?waybar-overrides\.css["\']?\);\s*\n?', "\n", text)
    marker = "\n/* Appearance overrides */"
    if marker in text:
        text = text.split(marker, 1)[0]
    return text.rstrip() + "\n"


def rebuild_style(state, has_settings):
    theme_path = theme_css_path()
    if theme_path != STYLE and theme_path.is_file():
        base = theme_path.read_text(encoding="utf-8")
    elif STYLE.is_file():
        base = STYLE.read_text(encoding="utf-8")
    else:
        base = ""

    base = strip_overrides(base)
    if has_settings:
        base = base.rstrip() + "\n\n/* Appearance overrides */\n" + render_overrides(state, True)
    STYLE.write_text(base, encoding="utf-8")


def generate(settings=None):
    if settings is None:
        settings = load_settings()
    state = effective_state(theme_defaults(), settings)
    OVERRIDES.parent.mkdir(parents=True, exist_ok=True)
    OVERRIDES.write_text(render_overrides(state, bool(settings)), encoding="utf-8")
    rebuild_style(state, bool(settings))
    return state, settings


def matching_brace(text, open_index):
    depth = 0
    in_string = False
    escaped = False
    for index in range(open_index, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        else:
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return index
    return -1


def find_blocks(text, key):
    pattern = re.compile(r'"' + re.escape(key) + r'"\s*:\s*\{')
    for match in pattern.finditer(text):
        open_index = match.end() - 1
        close_index = matching_brace(text, open_index)
        if close_index != -1:
            yield open_index, close_index


def get_justify(body):
    match = re.search(r'"justify"\s*:\s*"([^"]*)"', body)
    return match.group(1) if match else None


def set_justify(body, value):
    match = re.search(r'"justify"\s*:\s*"[^"]*"', body)
    if match:
        return body[: match.start()] + f'"justify": "{value}"' + body[match.end():]

    indent_match = re.search(r'\n([ \t]+)"', body)
    indent = indent_match.group(1) if indent_match else "      "
    stripped = body.rstrip()
    trailing = body[len(stripped):]
    if not stripped.strip():
        return f'\n{indent}"justify": "{value}"\n'
    separator = "" if stripped.endswith(",") else ","
    return stripped + f'{separator}\n{indent}"justify": "{value}"' + trailing


def remove_justify(body):
    match = re.search(r',\s*"justify"\s*:\s*"[^"]*"', body)
    if match:
        return body[: match.start()] + body[match.end():]
    match = re.search(r'"justify"\s*:\s*"[^"]*"\s*,?', body)
    if match:
        return body[: match.start()] + body[match.end():]
    return body


def collect_original(text):
    original = {}
    for key in MODULE_KEYS:
        values = [get_justify(text[open_index + 1:close_index]) for open_index, close_index in find_blocks(text, key)]
        if values:
            original[key] = values
    return original


def patch_config(text, alignment, original):
    changed = False
    for key in MODULE_KEYS:
        blocks = list(find_blocks(text, key))
        for index in range(len(blocks) - 1, -1, -1):
            open_index, close_index = blocks[index]
            body = text[open_index + 1:close_index]
            if alignment == "default":
                values = original.get(key, [])
                value = values[index] if index < len(values) else None
                new_body = remove_justify(body) if value is None else set_justify(body, value)
            else:
                new_body = set_justify(body, alignment)
            if new_body != body:
                text = text[: open_index + 1] + new_body + text[close_index:]
                changed = True
    return text, changed


def apply_alignment(settings):
    alignment = settings.get("text_align", "default")
    if alignment not in VALID_ALIGNMENTS:
        alignment = "default"
    if not CONFIG.is_file():
        return False

    text = CONFIG.read_text(encoding="utf-8")
    original = settings.get("_original_justify")
    if not isinstance(original, dict):
        original = {}

    if alignment == "default":
        if not original:
            return False
        new_text, _ = patch_config(text, "default", original)
    else:
        if not original:
            original = collect_original(text)
            settings["_original_justify"] = original
        new_text, _ = patch_config(text, alignment, original)
        settings["_original_justify"] = original

    if new_text == text:
        if alignment == "default":
            settings.pop("_original_justify", None)
        return False

    try:
        json.loads(new_text)
    except json.JSONDecodeError:
        return False

    CONFIG.write_text(new_text, encoding="utf-8")
    if alignment == "default":
        settings.pop("_original_justify", None)
    return True


def waybar_running():
    if not shutil.which("pgrep"):
        return False
    return subprocess.run(
        ["pgrep", "-x", "waybar"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def restart_waybar(start=False):
    if not start and not waybar_running():
        return
    if waybar_running():
        subprocess.run(["pkill", "-x", "waybar"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.25)
    if not shutil.which("waybar"):
        return
    command = ["waybar", "-c", str(CONFIG), "-s", str(STYLE)]
    try:
        if shutil.which("setsid"):
            subprocess.Popen(["setsid", "-f", *command], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
    except OSError:
        return
    if FOCUS.is_file():
        subprocess.run(["bash", str(FOCUS), "reset"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def apply():
    settings = load_settings()
    generate(settings)
    config_changed = apply_alignment(settings)
    save_settings(settings)
    if config_changed:
        restart_waybar(start=False)


def reset():
    settings = load_settings()
    original = settings.get("_original_justify")
    config_changed = False
    if isinstance(original, dict) and original and CONFIG.is_file():
        text = CONFIG.read_text(encoding="utf-8")
        new_text, _ = patch_config(text, "default", original)
        if new_text != text:
            try:
                json.loads(new_text)
            except json.JSONDecodeError:
                pass
            else:
                CONFIG.write_text(new_text, encoding="utf-8")
                config_changed = True
    SETTINGS.unlink(missing_ok=True)
    generate({})
    if config_changed:
        restart_waybar(start=False)


def print_state():
    settings = load_settings()
    state = effective_state(theme_defaults(), settings)
    output = {
        "bar_color": hex_color(state["bar_color"]),
        "bar_opacity": round(state["bar_opacity"], 3),
        "pill_color": hex_color(state["pill_color"]),
        "pill_opacity": round(state["pill_opacity"], 3),
        "text_color": hex_color(state["text_color"]),
        "bar_radius": state["bar_radius"],
        "pill_radius": state["pill_radius"],
        "text_align": state["text_align"],
    }
    print(json.dumps(output, indent=2))


def main(argv):
    command = argv[1] if len(argv) > 1 else "apply"
    quiet = "--quiet" in argv

    try:
        if command == "print":
            print_state()
        elif command == "generate":
            generate()
        elif command == "apply":
            apply()
        elif command == "reset":
            reset()
        elif command == "restart":
            restart_waybar(start=True)
        else:
            if not quiet:
                print("Usage: waybar-style.py [print|generate|apply|reset|restart] [--quiet]", file=sys.stderr)
            return 2
    except Exception as error:
        if not quiet:
            print(f"waybar-style: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
