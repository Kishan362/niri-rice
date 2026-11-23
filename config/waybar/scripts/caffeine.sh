
#!/usr/bin/env bash

PIDFILE="${XDG_RUNTIME_DIR:-/tmp}/waybar-caffeine.pid"

running() {
    [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null
}

if [[ "$1" == "toggle" ]]; then
    if running; then
        kill "$(cat "$PIDFILE")"
        rm -f "$PIDFILE"
    else
        systemd-inhibit \
            --what=idle:sleep \
            --who=Waybar \
            --why="Caffeine mode enabled" \
            --mode=block \
            sleep infinity &
        echo $! > "$PIDFILE"
    fi
    exit 0
fi

if running; then
    printf '{"text":"󰅶 ON","class":"activated","tooltip":"Caffeine enabled"}\n'
else
    printf '{"text":"󰾪 OFF","class":"deactivated","tooltip":"Caffeine disabled"}\n'
fi
