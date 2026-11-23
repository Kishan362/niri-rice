
#!/usr/bin/env bash

PIDFILE="${XDG_RUNTIME_DIR:-/tmp}/waybar-gammastep.pid"

running() {
    [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null
}

if [[ "$1" == "toggle" ]]; then
    if running; then
        kill "$(cat "$PIDFILE")"
        rm -f "$PIDFILE"
    else
        gammastep -m wayland \
            -l 23.02:72.57 \
            -t 6500:4000 &
        echo $! > "$PIDFILE"
    fi
    exit 0
fi

if running; then
    printf '{"text":"󰖔 ON","class":"active","tooltip":"Gammastep night light enabled"}\n'
else
    printf '{"text":"󰖔 OFF","class":"inactive","tooltip":"Gammastep night light disabled"}\n'
fi
