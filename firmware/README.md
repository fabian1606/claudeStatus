# Claude Buddy – Firmware (ESP32-C3 Super Mini)

Zwei WS2812B-Augen (GPIO 4, linkes Auge zuerst) zeigen den Gesamtstatus aller Claude-Code-Sessions.
Die Schnittstelle ist in `../CONTRACT.md` festgelegt.

| Zustand   | Augen |
|-----------|-------|
| idle      | sehr schwaches warmweiß/orange, langsames Atmen (~6 s) |
| working   | Claude-Orange (#D97757), weiches Pulsieren (~1,5 s) |
| attention | schnelles Blinken in Amber (~3 Hz) |
| done      | 2× hellgrüner Blitz, danach ruhiges, sanftes Grün |
| Start     | Augen faden in Orange ein |
| WLAN-Setup-Portal | langsames blaues Blinken (1 s an / 1 s aus) |
| WLAN verbindet | schwaches blaues Atmen |
| BOOT gehalten | Rot wird heller, bei 5 s rotes Flackern → Reset |

Priorität: attention > working > done > idle. In idle/working/done „zwinkern“ die Augen alle 4–10 s (120 ms aus).

## Bauen & Flashen

Mit PlatformIO (empfohlen):

```bash
cd firmware
pio run                 # bauen
pio run -t upload       # flashen (ESP32-C3 per USB-C anstecken)
pio device monitor      # serielle Logs (115200)
```

Falls der Upload nicht startet: **BOOT** gedrückt halten, kurz **RESET** drücken, BOOT loslassen
(Download-Modus), dann `pio run -t upload` erneut ausführen. Danach einmal RESET drücken.

Hinweise:
- Board `esp32-c3-devkitm-1`, Arduino-ESP32-Core 2.0.17 (`espressif32@6.13.0`), Flash-Modus DIO.
- `ARDUINO_USB_CDC_ON_BOOT=1` → `Serial` läuft über den nativen USB-C-Port.

**Arduino IDE (nicht getestet, PlatformIO ist der unterstützte Weg):** Board „ESP32C3 Dev Module“,
*USB CDC On Boot: Enabled*, *Flash Mode: DIO*, ESP32-Core **2.0.x** (der `/hook`-Handler nutzt die
`RequestHandler`-API von Core 2.x; Core 3.x hat andere Signaturen). Bibliotheken: Adafruit NeoPixel,
WiFiManager (tzapu) und ArduinoJson 7. Alle Dateien aus `src/` in einen Sketch-Ordner kopieren und
`main.cpp` in `<Ordnername>.ino` umbenennen.

## Erste WLAN-Einrichtung

1. Buddy per USB-C mit Strom versorgen. Ohne gespeichertes WLAN blinken die Augen langsam blau.
2. Mit dem Handy/Laptop ins WLAN **`Claude-Buddy-Setup`** (offen) gehen. Das Captive Portal öffnet sich,
   sonst http://192.168.4.1 aufrufen.
3. „Configure WiFi“ → Netz wählen, Passwort eingeben, speichern.
4. Der Buddy verbindet sich und ist dann unter **http://claude-buddy.local** erreichbar
   (die IP-Adresse steht auch im seriellen Log).

Nur 2,4-GHz-Netze funktionieren (ESP32-C3).

Verhalten im Betrieb:
- Ist ein WLAN gespeichert, aber 20 s lang nicht erreichbar, öffnet sich das Portal für 3 min.
  Danach versucht der Buddy wieder das gespeicherte WLAN (Schleife, bis es klappt).
- Bricht die Verbindung später ab, verbindet er sich im Hintergrund neu (Versuch alle 30 s).
  Die Augen zeigen dabei weiter den letzten Status.

## WLAN zurücksetzen

**BOOT-Taste (GPIO 9) im laufenden Betrieb 5 s gedrückt halten.** Ab 0,5 s leuchten die Augen rot
und werden heller, bei 5 s flackern sie rot. Die WLAN-Zugangsdaten werden gelöscht, der Buddy startet
neu und öffnet das Setup-Portal.
Wichtig: BOOT erst *nach* dem Einschalten drücken. Wird BOOT beim Einschalten/Reset gehalten,
startet der ESP im Download-Modus.

Alternativ über die serielle Konsole: `reset-wifi`.

## API testen (curl)

```bash
B=http://claude-buddy.local    # oder die IP, z. B. http://192.168.1.42

# Status
curl $B/status

# Hook-Events simulieren
curl -X POST $B/hook -H 'Content-Type: application/json' \
  -d '{"session_id":"test-1","hook_event_name":"UserPromptSubmit"}'      # -> working
curl -X POST $B/hook -H 'Content-Type: application/json' \
  -d '{"session_id":"test-1","hook_event_name":"Notification","notification_type":"permission_prompt","message":"Claude needs your permission"}'  # -> attention
curl -X POST $B/hook -H 'Content-Type: application/json' \
  -d '{"session_id":"test-1","hook_event_name":"Stop"}'                  # -> done
curl -X POST $B/hook -H 'Content-Type: application/json' \
  -d '{"session_id":"test-1","hook_event_name":"SessionEnd"}'            # Session entfernt

# Animation 5 s lang vorschauen
curl "$B/test?state=attention"

# Helligkeit setzen (0–255, wird gespeichert; Standard 60)
curl "$B/brightness?value=40"
```

Event-Zuordnung (siehe CONTRACT.md):
- `SessionStart` → idle
- `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `SubagentStop` → working
- `Notification`, `PermissionRequest` → attention. Ausnahme: `Notification` mit
  `notification_type` = `idle_prompt` oder `auth_success` wird ignoriert.
- `Stop`, `StopFailure` → done
- `SubagentStop` auf einer Session, die schon done oder idle ist (oder unbekannt ist), wird ignoriert.
- `SessionEnd` → Session wird entfernt. Unbekannte Events werden ignoriert (trotzdem 200).

Timeouts: working/attention ohne Event für 15 min → idle; done → nach 10 min idle; 2 h ohne Event →
Session wird entfernt. Es werden maximal 16 Sessions gespeichert, bei mehr fliegt die älteste raus.

Große Payloads: Vom Body werden die ersten 16 KB ausgewertet, der Rest wird gelesen und verworfen.
Ist der Body abgeschnitten oder kein gültiges JSON, sucht die Firmware `hook_event_name`, `session_id`
und `notification_type` per Textsuche. Der Body muss eine `Content-Length` haben (curl und die
üblichen HTTP-Clients setzen sie; *chunked* Uploads werden nicht unterstützt).

## Serielle Konsole (USB, 115200 Baud)

Jede Zeile, die mit `{` beginnt, wird wie ein `POST /hook`-Body verarbeitet:

```
{"session_id":"s1","hook_event_name":"PreToolUse"}
```

Weitere Befehle: `status`, `test <idle|working|attention|done>`, `brightness <0-255>`, `wifi`,
`reset-wifi`, `reboot`. Alle Events und Zustandswechsel werden geloggt.

## Code-Struktur

- `src/main.cpp` – Setup, nicht-blockierende WLAN-Zustandsmaschine (WiFiManager), BOOT-Taste, serielle Konsole
- `src/sessions.{h,cpp}` – Session-Tabelle (16 Plätze), Event-Zuordnung, Timeouts, Gesamtstatus
- `src/hook.{h,cpp}` – Hook-JSON auswerten (ArduinoJson-Filter, Textsuche als Fallback)
- `src/leds.{h,cpp}` – Animationen auf Basis von millis(), Überblendungen, Zwinkern
- `src/web.{h,cpp}` – HTTP-API und Statusseite
- `src/settings.{h,cpp}` – Helligkeit in NVS speichern (Preferences)
- `src/config.h` – Pins, Timeouts, Grenzwerte

## Animationen anpassen
Auf `http://claude-buddy.local` (oder der IP) gibt es die Karte **Animationen**: pro Zustand (Idle, Arbeitet, Achtung, Fertig)
Effekt, Farbe, Tempo, Min-/Max-Helligkeit und Zwinkern einstellen. Änderungen werden sofort als Vorschau gezeigt und
dauerhaft gespeichert; „Standard“ setzt zurück.

Effekte: `solid`, `breathe`, `blink`, `flash` (2 Blitze, dann an), `scanner` (Lauflicht), `wave`, `rainbow`, `sparkle`.

API:
```
curl http://claude-buddy.local/anim                                   # alle Einstellungen (JSON)
curl "http://claude-buddy.local/anim/set?state=working&effect=scanner&color=d97757&period=1200&lo=5&hi=100&blink=0"
curl "http://claude-buddy.local/anim/reset?state=working"             # ein Zustand auf Standard
curl  http://claude-buddy.local/anim/reset                            # alle auf Standard
```
`/anim/set` nimmt nur die übergebenen Felder; `save=0` zeigt nur eine Vorschau ohne zu speichern.

Hinweis: Auf macOS dauert die Auflösung von `claude-buddy.local` per curl ~5 s. Für die Hooks besser die feste IP
eintragen (`host/install.sh --url http://<IP>`) und im Router eine feste IP für den Buddy vergeben.
