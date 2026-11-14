# Claude Buddy

Kleine Claude-Figur für den Monitor. Die Augen zeigen, was Claude Code gerade macht – über alle offenen Sessions hinweg.

| Augen | Bedeutung |
|---|---|
| 🟠🔴 schnelles Blinken | Claude **wartet auf dich** (Berechtigung / Rückfrage) |
| 🟠 ruhiges Pulsieren | Claude **arbeitet** |
| 🟢 grüner Blitz, dann leises Grün | Claude ist **fertig** |
| ⚪ ganz schwaches Atmen | nichts los |
| 🔵 langsames Blinken | WLAN-Einrichtung aktiv |

Bei mehreren Sessions gewinnt die wichtigste: *wartet* > *arbeitet* > *fertig* > *idle*.

## Wie es funktioniert
```
Claude Code ──Hook──▶ claude-buddy-hook.sh ──USB-Kabel (seriell)──▶ ESP32-C3 ──▶ 6 NeoPixel
                                   WLAN nur für die Weboberfläche (Animationen einstellen)
```
Der Hook braucht ~40 ms und tut nichts, wenn der Buddy nicht angesteckt ist.

## Projektstruktur
- [firmware/](firmware/) – PlatformIO-Projekt für den ESP32-C3 Super Mini → [Anleitung](firmware/README.md)
- [host/](host/) – Hook-Skript, Installer, Mock-Gerät zum Testen ohne Hardware → [Anleitung](host/README.md)
- [cad/](cad/) – Fusion-Skript fürs Gehäuse, Druck- und Montageanleitung → [Anleitung](cad/README.md)
- [CONTRACT.md](CONTRACT.md) – Schnittstelle zwischen allen Teilen (API, Events, Pins)

## Stückliste
| Teil | Menge |
|---|---|
| ESP32-C3 Super Mini (USB-C) | 1 |
| WS2812B-LED-Streifen, 60 LEDs/m, 5 V | 6 LEDs |
| Litze, dünn (z. B. 28–30 AWG), 3 Farben | ~20 cm |
| Schrauben M2×8 selbstschneidend (oder ST2.2×8) | 4 |
| **Version A:** PLA transluzent orange (oder weiß/natur) + schwarz (Augen) | wenig |
| **Version B:** PLA weiß (Front) + schwarz (Gehäuse, Augen, Deckel) | wenig |
| Heißkleber, doppelseitiges Klebeband, USB-C-Kabel | – |

## Verdrahtung
```
ESP32-C3 Super Mini            LED links (Eye_L)          LED rechts (Eye_R)
  5V   ─────────────────────▶  +5V ───────────────────▶  +5V
  GND  ─────────────────────▶  GND ───────────────────▶  GND
  GPIO 5 ───────────────────▶  DIN    DOUT ───────────▶  DIN   … (6 LEDs in Reihe)
```
Pfeilrichtung auf dem Streifen beachten (DIN → DOUT). Die linke LED (vom Betrachter aus) ist die erste.

## Inbetriebnahme – Kurzfassung
1. **Gehäuse:** fertige Dateien liegen in `cad/ClaudeBuddy/export/A_lightbox/` bzw. `B_whitefront/` (3MF/STEP in Bambu Studio öffnen, Augen = schwarz, Front nach unten drucken). Details: [cad/README.md](cad/README.md).
2. **Firmware:** `cd firmware && pio run -t upload`
3. **WLAN:** Mit dem Handy ins WLAN „Claude-Buddy-Setup“ → Heimnetz (2,4 GHz) wählen.
4. **Test:** `http://claude-buddy.local` im Browser → Test-Buttons.
5. **Hooks:** `cd host && ./install.sh` (macht ein Backup der `~/.claude/settings.json`). Buddy per USB am Rechner lassen – Claude-Code-Sessions melden sich dann automatisch.
6. **Montage:** LED-Stücke auf die Innenseite des Rückdeckels kleben, ESP in die Bodentasche (Heißkleber), verlöten, Deckel mit 4 Schrauben zu, mit Klebeband auf den Monitor.

Ohne Hardware testen: `python3 host/mock_buddy.py` und `CLAUDE_BUDDY_URL=http://localhost:8787` setzen.

## Bekannte offene Punkte
- Firmware ist kompiliert, aber noch nicht auf echter Hardware getestet.
- Gehäuse (beide Versionen) in Fusion gebaut und geprüft: 60 × 30 mm (+7,5 mm Beine) × 26 mm, ESP als Referenzmodell drin, USB-C-Buchse bündig im passgenauen Loch – aber noch nicht gedruckt.
- USB-C-Loch hat 0,2 mm Luft pro Seite (`usb_clr`); Überstand der Buchse über die Platine (0,8 mm angenommen) am echten Board nachmessen → `usb_overhang`.
- Die Front ist direkt vor den beiden LEDs etwas heller; Beine leuchten kaum.
