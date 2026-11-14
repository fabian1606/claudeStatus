#!/bin/sh
# uninstall.sh - removes only the Claude Buddy hook entries from Claude Code.
#
#   ./uninstall.sh [--claude-dir DIR] [--settings FILE] [--keep-script] [--purge-config]
#
#   --claude-dir DIR  Claude config dir (default: $CLAUDE_CONFIG_DIR or ~/.claude)
#   --settings FILE   settings.json to modify (default: DIR/settings.json,
#                     env: CLAUDE_BUDDY_SETTINGS)
#   --keep-script     do not delete DIR/claude-buddy/
#   --purge-config    also delete ${CLAUDE_BUDDY_CONF:-~/.claude-buddy.conf}
#
# Other hooks and settings stay untouched. A timestamped backup is written first.
set -eu

claude_dir="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
settings="${CLAUDE_BUDDY_SETTINGS:-}"
keep_script=0
purge_config=0

while [ $# -gt 0 ]; do
    case "$1" in
        --claude-dir)   claude_dir="$2"; shift 2 ;;
        --settings)     settings="$2"; shift 2 ;;
        --keep-script)  keep_script=1; shift ;;
        --purge-config) purge_config=1; shift ;;
        -h|--help)      sed -n '2,12p' "$0"; exit 0 ;;
        *) echo "Unbekannte Option: $1" >&2; exit 2 ;;
    esac
done
[ -n "$settings" ] || settings="$claude_dir/settings.json"

command -v python3 >/dev/null 2>&1 || { echo "Fehler: python3 wird benoetigt." >&2; exit 1; }

if [ -f "$settings" ]; then
python3 - "$settings" <<'PY'
import json, os, shutil, sys, time

settings_path = sys.argv[1]
MARKER = "claude-buddy-hook.sh"

with open(settings_path, encoding="utf-8") as f:
    text = f.read()
try:
    data = json.loads(text) if text.strip() else {}
except json.JSONDecodeError as e:
    sys.exit(f"Fehler: {settings_path} ist kein gueltiges JSON ({e}). Nichts geaendert.")

hooks = data.get("hooks") if isinstance(data, dict) else None
if not isinstance(hooks, dict):
    print(f"{settings_path}: keine Hooks vorhanden - nichts zu tun.")
    sys.exit(0)

removed = 0
for ev in list(hooks):
    groups = hooks[ev]
    if not isinstance(groups, list):
        continue
    kept_groups = []
    for g in groups:
        if isinstance(g, dict) and isinstance(g.get("hooks"), list):
            before = len(g["hooks"])
            g["hooks"] = [h for h in g["hooks"]
                          if not (isinstance(h, dict) and MARKER in str(h.get("command", "")))]
            n = before - len(g["hooks"])
            removed += n
            if n and not g["hooks"]:
                continue            # group only contained our hook -> drop it
        kept_groups.append(g)
    if kept_groups:
        hooks[ev] = kept_groups
    elif groups:                    # event became empty because of us
        del hooks[ev]
if not hooks:
    del data["hooks"]

if removed == 0:
    print(f"{settings_path}: keine Claude-Buddy-Eintraege gefunden - nichts geaendert.")
    sys.exit(0)

backup = f"{settings_path}.bak-claude-buddy-{time.strftime('%Y%m%d-%H%M%S')}"
shutil.copy2(settings_path, backup)
tmp = settings_path + ".tmp-claude-buddy"
with open(tmp, "w", encoding="utf-8") as f:
    f.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
os.replace(tmp, settings_path)
print(f"Backup: {backup}")
print(f"{settings_path}: {removed} Claude-Buddy-Eintraege entfernt.")
PY
else
    echo "$settings existiert nicht - nichts zu tun."
fi

if [ "$keep_script" -eq 0 ] && [ -d "$claude_dir/claude-buddy" ]; then
    rm -f "$claude_dir/claude-buddy/claude-buddy-hook.sh"
    rmdir "$claude_dir/claude-buddy" 2>/dev/null || echo "Hinweis: $claude_dir/claude-buddy nicht leer, bleibt bestehen."
    echo "Hook-Skript entfernt."
fi

if [ "$purge_config" -eq 1 ]; then
    conf="${CLAUDE_BUDDY_CONF:-$HOME/.claude-buddy.conf}"
    rm -f "$conf" && echo "Konfiguration entfernt: $conf"
fi
