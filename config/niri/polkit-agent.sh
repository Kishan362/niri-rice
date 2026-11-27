#!/usr/bin/env bash
set -euo pipefail

for agent in \
    /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1 \
    /usr/libexec/polkit-gnome-authentication-agent-1 \
    /usr/libexec/polkit-mate-authentication-agent-1 \
    /usr/lib/polkit-1/polkit-agent-1; do
    if [ -x "$agent" ]; then
        exec "$agent"
    fi
done

printf 'No polkit authentication agent found\n' >&2
exit 1
