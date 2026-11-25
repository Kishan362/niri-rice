#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$DIR/settings.py" ] && python3 -c 'import gi; gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")' >/dev/null 2>&1; then
    exec python3 "$DIR/settings.py" "$@"
fi

exec "$DIR/menu.sh" "$@"
