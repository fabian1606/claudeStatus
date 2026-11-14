#!/bin/sh
# claude-buddy-hook.sh - forwards Claude Code hook events to the Claude Buddy over USB.
#
# Claude Code pipes the hook JSON to stdin. We extract the three fields the
# Buddy needs (session_id, hook_event_name, notification_type) and write them
# as one compact JSON line to the Buddy's USB serial port. WiFi is only used
# for the Buddy's web UI (animation editor), not for events.
#
# Rules: never print to stdout (SessionStart/UserPromptSubmit stdout would be
# injected into Claude's context), never exit non-zero, never block.
#
# Config (env var or KEY=value line in ${CLAUDE_BUDDY_CONF:-~/.claude-buddy.conf}):
#   CLAUDE_BUDDY_PORT=/dev/cu.usbmodem101   fixed serial port (default: auto-detect)
#   CLAUDE_BUDDY_DISABLED=1                 turn forwarding off

exec 1>/dev/null 2>/dev/null

conf_get() {
    # conf_get KEY FILE -> value of KEY=value (last occurrence), quotes stripped.
    # The file is parsed, not sourced, so it cannot run code or print anything.
    sed -n "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*//p" "$2" 2>/dev/null \
        | tail -n 1 \
        | sed -e 's/[[:space:]]*$//' -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'\$/\1/"
}

conf="${CLAUDE_BUDDY_CONF:-$HOME/.claude-buddy.conf}"
if [ -r "$conf" ]; then
    [ -n "$CLAUDE_BUDDY_PORT" ] || CLAUDE_BUDDY_PORT=$(conf_get CLAUDE_BUDDY_PORT "$conf")
    [ -n "$CLAUDE_BUDDY_DISABLED" ] || CLAUDE_BUDDY_DISABLED=$(conf_get CLAUDE_BUDDY_DISABLED "$conf")
fi

case "$CLAUDE_BUDDY_DISABLED" in 1|true|yes|on)
    cat >/dev/null 2>&1
    exit 0 ;;
esac

# Only the head of the payload is needed: the top-level fields come before
# tool_input / tool_response. Drain the rest so Claude Code never sees EPIPE.
payload=$(head -c 8192 2>/dev/null)
cat >/dev/null 2>&1

field() {
    # first occurrence of "key": "value" (JSON is a single line, so grep -o + head)
    printf '%s' "$payload" | grep -o "\"$1\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" | head -n 1 \
        | sed 's/.*"\([^"]*\)"$/\1/' | tr -cd "$2"
}
sid=$(field session_id 'A-Za-z0-9_.-')
ev=$(field hook_event_name 'A-Za-z')
nt=$(field notification_type 'a-z_')
[ -n "$ev" ] || exit 0
[ -n "$sid" ] || sid=unknown

# --- find the Buddy's serial port ---
port="$CLAUDE_BUDDY_PORT"
if [ -z "$port" ]; then
    if command -v ioreg >/dev/null 2>&1; then
        # macOS: the ESP32-C3's built-in USB serial/JTAG unit
        port=$(ioreg -r -c IOUSBHostDevice -l -w0 2>/dev/null \
            | awk '/"USB Product Name" = "USB JTAG\/serial debug unit"/{f=1}
                   f && /IOCalloutDevice/{gsub(/.*= "|"$/, ""); print; exit}')
    else
        # Linux
        for p in /dev/serial/by-id/*Espressif* /dev/serial/by-id/*JTAG*; do
            [ -e "$p" ] && { port="$p"; break; }
        done
    fi
fi
[ -n "$port" ] && [ -w "$port" ] || exit 0

line="{\"session_id\":\"$sid\",\"hook_event_name\":\"$ev\""
[ -n "$nt" ] && line="$line,\"notification_type\":\"$nt\""
line="$line}"

# Serialize writers (parallel hooks from several sessions) with a mkdir lock.
lock="${TMPDIR:-/tmp}/claude-buddy.lock"
i=0
while ! mkdir "$lock" 2>/dev/null; do
    i=$((i + 1))
    if [ "$i" -ge 50 ]; then rm -rf "$lock" 2>/dev/null; mkdir "$lock" 2>/dev/null; break; fi  # stale lock
    sleep 0.02 2>/dev/null || sleep 1
done
printf '%s\n' "$line" >"$port" 2>/dev/null
rmdir "$lock" 2>/dev/null

exit 0
