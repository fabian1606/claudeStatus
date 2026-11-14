#!/bin/sh
# install.sh - installs the Claude Buddy hook for Claude Code.
#
#   ./install.sh [--claude-dir DIR] [--settings FILE] [--url URL] [--dry-run]
#
#   --claude-dir DIR  Claude config dir (default: $CLAUDE_CONFIG_DIR or ~/.claude).
#                     The hook script is copied to DIR/claude-buddy/.
#   --settings FILE   settings.json to modify (default: DIR/settings.json,
#                     env: CLAUDE_BUDDY_SETTINGS).
#   --url URL         also write CLAUDE_BUDDY_URL=URL to the config file
#                     (${CLAUDE_BUDDY_CONF:-~/.claude-buddy.conf}), e.g. http://192.168.1.50
#   --dry-run         print the resulting settings.json instead of writing it.
#
# Idempotent: re-running updates our entries instead of duplicating them.
# A timestamped backup of settings.json is written before every change.
set -eu

here=$(cd "$(dirname "$0")" && pwd)
claude_dir="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
settings="${CLAUDE_BUDDY_SETTINGS:-}"
url=""
dry_run=0

while [ $# -gt 0 ]; do
    case "$1" in
        --claude-dir) claude_dir="$2"; shift 2 ;;
        --settings)   settings="$2"; shift 2 ;;
        --url)        url="$2"; shift 2 ;;
        --dry-run)    dry_run=1; shift ;;
        -h|--help)    sed -n '2,16p' "$0"; exit 0 ;;
        *) echo "Unbekannte Option: $1" >&2; exit 2 ;;
    esac
done
[ -n "$settings" ] || settings="$claude_dir/settings.json"

command -v python3 >/dev/null 2>&1 || { echo "Fehler: python3 wird benoetigt." >&2; exit 1; }
command -v curl >/dev/null 2>&1 || echo "Warnung: curl nicht gefunden - der Hook sendet ohne curl nichts." >&2

install_dir="$claude_dir/claude-buddy"
hook="$install_dir/claude-buddy-hook.sh"

# Validate settings.json BEFORE touching anything on disk.
if [ -f "$settings" ]; then
    python3 - "$settings" <<'PY' || exit 1
import json, sys
p = sys.argv[1]
text = open(p, encoding="utf-8").read()
if text.strip():
    try:
        d = json.loads(text)
    except json.JSONDecodeError as e:
        sys.exit(f"Fehler: {p} ist kein gueltiges JSON ({e}). Nichts geaendert.")
    if not isinstance(d, dict) or not isinstance(d.get("hooks", {}), dict):
        sys.exit(f"Fehler: {p} hat eine unerwartete Struktur. Nichts geaendert.")
PY
fi

if [ "$dry_run" -eq 0 ]; then
    mkdir -p "$install_dir"
    cp "$here/claude-buddy-hook.sh" "$hook"
    chmod 755 "$hook"
    echo "Hook-Skript installiert: $hook"
fi

python3 - "$settings" "$hook" "$dry_run" <<'PY'
import json, os, shlex, shutil, sys, time

settings_path, hook_path, dry_run = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
MARKER = "claude-buddy-hook.sh"
EVENTS = ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse",
          "Notification", "PermissionRequest", "Stop", "StopFailure", "SubagentStop",
          "SessionEnd"]
handler = {"type": "command", "command": shlex.quote(hook_path), "timeout": 5}

data = {}
text = None
if os.path.exists(settings_path):
    with open(settings_path, encoding="utf-8") as f:
        text = f.read()
    if text.strip():
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            sys.exit(f"Fehler: {settings_path} ist kein gueltiges JSON ({e}). Nichts geaendert.")
if not isinstance(data, dict):
    sys.exit(f"Fehler: {settings_path} enthaelt kein JSON-Objekt. Nichts geaendert.")

hooks = data.setdefault("hooks", {})
if not isinstance(hooks, dict):
    sys.exit("Fehler: 'hooks' in settings.json ist kein Objekt. Nichts geaendert.")

def is_ours(h):
    return isinstance(h, dict) and MARKER in str(h.get("command", ""))

added = updated = 0
for ev in EVENTS:
    groups = hooks.setdefault(ev, [])
    if not isinstance(groups, list):
        sys.exit(f"Fehler: hooks.{ev} ist keine Liste. Nichts geaendert.")
    found = False
    emptied = set()
    for g in groups:
        if not isinstance(g, dict) or not isinstance(g.get("hooks"), list):
            continue
        before = len(g["hooks"])
        new_list = []
        for h in g["hooks"]:
            if is_ours(h):
                if found:
                    continue            # drop duplicates of our entry
                found = True
                if h != handler:
                    updated += 1
                h = dict(handler)
            new_list.append(h)
        g["hooks"] = new_list
        if before and not new_list:
            emptied.add(id(g))
    # remove groups we emptied by de-duplication
    hooks[ev] = [g for g in groups if id(g) not in emptied]
    if not found:
        hooks[ev].append({"hooks": [dict(handler)]})
        added += 1

out = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
if dry_run:
    print(out, end="")
    sys.exit(0)

if text is not None and out == text:
    print(f"{settings_path}: bereits aktuell - nichts geaendert.")
    sys.exit(0)

os.makedirs(os.path.dirname(os.path.abspath(settings_path)), exist_ok=True)
if os.path.exists(settings_path):
    backup = f"{settings_path}.bak-claude-buddy-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(settings_path, backup)
    print(f"Backup: {backup}")
tmp = settings_path + ".tmp-claude-buddy"
with open(tmp, "w", encoding="utf-8") as f:
    f.write(out)
os.replace(tmp, settings_path)
print(f"{settings_path}: {added} Hook-Eintraege hinzugefuegt, {updated} aktualisiert, "
      f"{len(EVENTS) - added - updated} unveraendert.")
PY

if [ -n "$url" ] && [ "$dry_run" -eq 0 ]; then
    conf="${CLAUDE_BUDDY_CONF:-$HOME/.claude-buddy.conf}"
    if [ -f "$conf" ] && grep -q '^[[:space:]]*CLAUDE_BUDDY_URL[[:space:]]*=' "$conf"; then
        tmpc="$conf.tmp.$$"
        grep -v '^[[:space:]]*CLAUDE_BUDDY_URL[[:space:]]*=' "$conf" >"$tmpc" || true
        echo "CLAUDE_BUDDY_URL=$url" >>"$tmpc"
        mv "$tmpc" "$conf"
    else
        echo "CLAUDE_BUDDY_URL=$url" >>"$conf"
    fi
    echo "Konfiguration geschrieben: $conf (CLAUDE_BUDDY_URL=$url)"
fi

if [ "$dry_run" -eq 0 ]; then
    echo "Fertig. Laufende Claude-Code-Sitzungen neu starten (oder /hooks oeffnen), damit die Hooks aktiv werden."
fi
