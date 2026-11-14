# Claude Buddy – Host-Teil (Claude Code Hooks)

Dieser Ordner verbindet Claude Code mit der Claude-Buddy-Figur. Claude Code ruft bei jedem
relevanten Ereignis einen Hook auf. Der Hook schickt das Ereignis **über das USB-Kabel** (serielle
Schnittstelle) an den Buddy, und die LEDs zeigen den Gesamtstatus aller laufenden Sitzungen an.
WLAN wird nur für die Weboberfläche (Animations-Editor) gebraucht – der Buddy muss also per USB am
Rechner hängen, auf dem Claude Code läuft.

| Datei | Zweck |
|---|---|
| `claude-buddy-hook.sh` | Der Hook. Liest `session_id`, `hook_event_name` und `notification_type` aus dem JSON und schreibt sie als eine Zeile auf den USB-Port des Buddys (Port wird automatisch gefunden). Dauert ~40 ms, gibt nichts aus, endet immer mit Exit-Code 0, tut nichts, wenn der Buddy nicht angesteckt ist. |
| `install.sh` | Kopiert den Hook nach `~/.claude/claude-buddy/` und trägt ihn in `~/.claude/settings.json` ein. |
| `uninstall.sh` | Entfernt nur die Claude-Buddy-Einträge wieder. |
| `mock_buddy.py` | Simuliert das Gerät per HTTP (aus der früheren WLAN-Variante; für die USB-Hooks nicht mehr nötig). |

Voraussetzungen: `sh`, `curl` und `python3` (für Installer und Mock). Auf macOS ist alles vorinstalliert.
`jq` wird nicht benötigt.

## Installation

```sh
cd host
./install.sh
```

Was der Installer macht:

- Er kopiert den Hook nach `~/.claude/claude-buddy/claude-buddy-hook.sh`.
- Er legt ein Backup an: `~/.claude/settings.json.bak-claude-buddy-JJJJMMTT-HHMMSS`.
- Er trägt den Hook für diese Ereignisse ein: `SessionStart`, `UserPromptSubmit`, `PreToolUse`,
  `PostToolUse`, `Notification`, `PermissionRequest`, `Stop`, `StopFailure`, `SubagentStop` und `SessionEnd`.
- Vorhandene Hooks und Einstellungen bleiben erhalten.
- Mehrfaches Ausführen ist unproblematisch. Es entstehen keine doppelten Einträge. Ändert sich nichts,
  schreibt der Installer auch nichts und legt kein Backup an.

Danach laufende Claude-Code-Sitzungen neu starten. Mit `/hooks` in Claude Code siehst du, ob die Hooks aktiv sind.

Optionen:

```sh
./install.sh --url http://192.168.1.50      # feste IP direkt in ~/.claude-buddy.conf schreiben
./install.sh --claude-dir /pfad/zu/.claude  # anderes Claude-Verzeichnis (Standard: $CLAUDE_CONFIG_DIR oder ~/.claude)
./install.sh --settings /pfad/settings.json # andere settings.json (auch per CLAUDE_BUDDY_SETTINGS=…)
./install.sh --dry-run                      # zeigt das Ergebnis-JSON an, ohne etwas zu schreiben
```

Der Installer erzeugt pro Ereignis diesen Eintrag:

```json
"Stop": [ { "hooks": [ { "type": "command", "command": "'/Users/du/.claude/claude-buddy/claude-buddy-hook.sh'", "timeout": 5 } ] } ]
```

`async: true` ist absichtlich nicht gesetzt. Der Hook kehrt ohnehin sofort zurück, weil er `curl` selbst
in den Hintergrund schickt. Ein synchroner Hook, der sofort endet, ist zuverlässiger als ein async-Hook,
denn Claude Code beendet async-Hooks im `-p`-Modus beim Beenden.

## Konfiguration

Normalerweise nichts zu tun: Der Hook findet den Buddy automatisch
(macOS: USB-Gerät „USB JTAG/serial debug unit“ des ESP32-C3, Linux: `/dev/serial/by-id/*Espressif*`).

Optional in `~/.claude-buddy.conf` (wird nur gelesen, nicht ausgeführt):

```sh
# festen Port erzwingen
CLAUDE_BUDDY_PORT=/dev/cu.usbmodem101
# vorübergehend abschalten
# CLAUDE_BUDDY_DISABLED=1
```

Test von Hand:

```sh
printf '{"session_id":"test","hook_event_name":"UserPromptSubmit"}' | ~/.claude/claude-buddy/claude-buddy-hook.sh
# -> LEDs zeigen "arbeitet"; zurücksetzen mit hook_event_name "SessionEnd"
```

Hinweis: Solange ein Programm den Port exklusiv offen hat (z. B. der Serial Monitor von PlatformIO /
Arduino IDE), kommen keine Ereignisse an.

## Testen ohne Hardware

Terminal 1 startet das simulierte Gerät:

```sh
python3 host/mock_buddy.py                 # http://127.0.0.1:8787
python3 host/mock_buddy.py --timescale 600 # alle Timeouts 600x schneller (15 min → 1,5 s)
```

Terminal 2 schickt einzelne Ereignisse von Hand:

```sh
export CLAUDE_BUDDY_URL=http://localhost:8787
echo '{"session_id":"s1","hook_event_name":"UserPromptSubmit"}' | host/claude-buddy-hook.sh
echo '{"session_id":"s1","hook_event_name":"PermissionRequest","tool_name":"Bash"}' | host/claude-buddy-hook.sh
echo '{"session_id":"s1","hook_event_name":"Stop"}' | host/claude-buddy-hook.sh
curl -s localhost:8787/status
```

Oder mit echtem Claude Code: Installieren, `CLAUDE_BUDDY_URL=http://localhost:8787 claude` starten und arbeiten.
Der Mock zeigt jede Zustandsänderung farbig an. Unter http://localhost:8787/ gibt es außerdem eine kleine
Statusseite mit Test-Buttons.

## Zustände

| Ereignis | Zustand der Sitzung |
|---|---|
| `SessionStart` | idle (Sitzung wird angelegt) |
| `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `SubagentStop` | working |
| `Notification`, `PermissionRequest` | attention (außer `idle_prompt`/`auth_success`, siehe unten) |
| `Stop`, `StopFailure` (Runde wegen API-Fehler beendet) | done |
| `SessionEnd` | Sitzung wird entfernt |

Die Augen zeigen den „höchsten“ Zustand aller Sitzungen: **attention > working > done > idle**.

Zwei Sonderregeln (gelten laut CONTRACT.md für Gerät und Mock):

- `Notification` mit `notification_type` = `idle_prompt` oder `auth_success` ändert den Zustand nicht.
  `idle_prompt` kommt etwa 60 s nach jedem `Stop`. Ohne diese Regel würde jedes „done“ nach einer Minute
  zu „attention“ werden.
- `SubagentStop` wird ignoriert, wenn die Sitzung bereits auf done oder idle steht. Sie wird also nicht zurück auf working gesetzt.
  Das betrifft Hintergrund-Agenten, die erst nach dem `Stop` fertig werden.

Timeouts:

- working oder attention ohne neues Ereignis für 15 min → idle
- done → idle nach 10 min
- 2 h ohne Ereignis → Sitzung wird entfernt

## Deinstallation

```sh
cd host
./uninstall.sh                 # entfernt nur die Claude-Buddy-Einträge und das Hook-Skript (mit Backup)
./uninstall.sh --purge-config  # löscht zusätzlich ~/.claude-buddy.conf
```

`--claude-dir` und `--settings` funktionieren wie beim Installer.

## Fehlersuche

- **Erreiche ich das Gerät?**
  ```sh
  curl -m 3 http://claude-buddy.local/status
  curl -m 3 http://192.168.1.50/status        # mit fester IP
  ```
  Klappt das nur mit der IP, die IP in `~/.claude-buddy.conf` eintragen.
- **Augen testen:** `curl "http://claude-buddy.local/test?state=attention"` zeigt die Animation 5 s lang.
  Die Helligkeit stellst du mit `curl "http://claude-buddy.local/brightness?value=60"` ein.
- **Kommt der Hook überhaupt an?** Den Mock starten und `CLAUDE_BUDDY_URL=http://localhost:8787` setzen.
  In Claude Code mit `/hooks` prüfen, ob die Einträge da sind. `claude --debug` zeigt die Hook-Aufrufe.
- **Hook von Hand ausführen, ohne Hintergrund und mit sichtbarer Ausgabe:**
  ```sh
  echo '{"session_id":"x","hook_event_name":"Stop"}' > /tmp/ev.json
  curl -v -m 2 -X POST --data-binary @/tmp/ev.json -H 'Content-Type: application/json' http://claude-buddy.local/hook
  ```
- **Gerät nicht im WLAN:** Das Gerät öffnet den Access Point „Claude-Buddy-Setup“. Damit verbinden und
  im Captive Portal das WLAN einrichten.
- **Firmen-WLAN mit Client-Isolation:** Rechner und Buddy können sich dann nicht direkt erreichen.
  Ein anderes Netz verwenden, z. B. ein Gäste- oder Heimnetz.
- **Augen hängen auf working/attention fest:** Das passiert z. B. nach einem Absturz ohne `SessionEnd`.
  Nach 15 min fällt der Zustand automatisch auf idle zurück. Sofort hilft ein Neustart des Geräts.
- **Hook vorübergehend aus:** `CLAUDE_BUDDY_DISABLED=1` in `~/.claude-buddy.conf` eintragen.
