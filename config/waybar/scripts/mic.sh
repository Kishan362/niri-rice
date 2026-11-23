
#!/usr/bin/env bash

if [[ "$1" == "toggle" ]]; then
    pactl set-source-mute @DEFAULT_SOURCE@ toggle
    exit 0
fi

if pactl get-source-mute @DEFAULT_SOURCE@ | grep -q yes; then
    printf '{"text":"󰍭 MIC","class":"muted","tooltip":"Microphone muted"}\n'
else
    printf '{"text":"󰍬 MIC","class":"active","tooltip":"Microphone active"}\n'
fi
