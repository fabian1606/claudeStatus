# Claude Buddy – Gehäuse (Fusion-Skript)

Parametrisches Gehäuse in Form des Claude-Code-Maskottchens „Clawd“ (Pixel-Art), das oben auf dem Monitor sitzt. Die **ganze Front leuchtet** (Leuchtkasten), die Augen sind dunkle Einleger. Zwei WS2812B-Streifenstücke sitzen innen auf dem Rückdeckel und strahlen nach vorne. Die Farbe zeigt den Claude-Code-Status an.

Es gibt zwei Varianten mit identischem Innenleben:

| Variante | Fusion-Dokument | Farben | Export-Ordner |
|---|---|---|---|
| **A – Leuchtkasten** | `ClaudeBuddy_A_Lightbox` | Body transluzent orange (oder weiß/natur), Augen schwarz | `export/A_lightbox/` |
| **B – weiße Front** | `ClaudeBuddy_B_WhiteFront` | FrontPlate weiß, Housing + Augen + Deckel schwarz | `export/B_whitefront/` |

```
cad/
├── ClaudeBuddy/
│   ├── ClaudeBuddy.py         ← Fusion-Python-Skript (baut beide Varianten, einzige Quelle der Maße)
│   ├── ClaudeBuddy.manifest   ← Skript-Manifest für Fusion
│   └── export/
│       ├── A_lightbox/        ← STEP, 3MF, Body/Eye_L/Eye_R/BackCover.stl, ESP32C3_ref.step
│       └── B_whitefront/      ← STEP, 3MF, FrontPlate/Housing/Eye_L/Eye_R/BackCover.stl, front_outline.dxf, ESP32C3_ref.step
├── preview/
│   ├── render_preview.py      ← 2D-Vorschau ohne Fusion (matplotlib)
│   └── preview.png            ← Ansichten/Schnitte mit den Default-Maßen
└── README.md
```

## Maße (Defaults, px = 3,75 mm, in Fusion nachgemessen)

| | |
|---|---|
| Gesamtbreite inkl. Arm-Stummel | **60,0 mm** (Körper 45,0 mm + 2 × 7,5 mm Arme) |
| Körperhöhe | **30,0 mm** (+ 7,5 mm Beinchen nach unten) |
| Tiefe | **24,12 mm** Body + 2,0 mm Deckel = **26,12 mm** |
| Front-Diffusor (`front_t`) | 1,2 mm |
| Seiten-/Deckenwand (`wall`) | 2,0 mm, Boden (`floor_t`) 2,4 mm (unter der ESP-Tasche bleiben 1,4 mm) |
| Lichtweg LED → Diffusor | **21,3 mm** |
| USB-C-Loch | **9,34 × 3,66 mm**, Stadionform (Buchse 8,94 × 3,26 + 0,2 mm je Seite), geschlossen |
| Augen | 3,75 × 7,5 mm, 2,0 mm tief (1,2 mm durch die Front + 0,8 mm nach innen) |

Warum diese Tiefe? Der ESP32-C3 Super Mini (22,52 mm) liegt längs im Boden, damit USB-C hinten herauskommt. Er ist ganz nach hinten geschoben: Die Front der USB-C-Buchse liegt **bündig mit der Außenseite des Deckels**. Die Tiefe ergibt sich also aus Front + Taschen-Vorderwand + ESP + USB-Überstand. Die LEDs sitzen ganz hinten auf dem Deckel. So entsteht ein langer Lichtweg und die Front wird gleichmäßig ausgeleuchtet.

## Skript ausführen

1. Fusion öffnen → **Dienstprogramme → Add-Ins → Skripte und Zusatzmodule** (Shift+S).
2. Unter „Skripte“ auf **+** klicken (bzw. „Skript oder Add-In vom Gerät“) und den Ordner `cad/ClaudeBuddy` auswählen.
3. `ClaudeBuddy` auswählen → **Ausführen**.
4. Das Skript legt **pro Variante ein neues Design** an. Jedes enthält zusätzlich die Komponente **`ESP32C3_SuperMini_REF`**: ein Referenzmodell des ESP (Platine, USB-C-Buchse mit runden Enden, Chip, Tasten, Antenne) in Einbaulage. Es ist nur zur Kontrolle da und wird **nicht** in die Druckdateien exportiert, sondern separat als `ESP32C3_ref.step`. Wer später von Hand aus Fusion exportiert, blendet die Komponente vorher aus.

   Welche Varianten gebaut werden, steht in `BUILD_VARIANTS` (`BUILD_VARIANTS = ("A", "B")` oben im Build-Teil des Skripts; z. B. `("B",)` baut nur Variante B). Jedes Dokument bekommt alle Benutzerparameter und die Körper. Danach wird nach `cad/ClaudeBuddy/export/<Variante>/` exportiert: STEP, 3MF, eine STL pro Körper und bei B zusätzlich `front_outline.dxf`.
5. Am Ende erscheint eine Meldung mit den Gesamtmaßen, dem Lichtweg und eventuellen Warnungen. Bei einem Fehler zeigt die Meldung den Traceback.

Die Dokumente werden **nicht** automatisch in der Cloud gespeichert. Speichere sie bei Bedarf selbst (Datei → Speichern, Projekt wählen).

Koordinaten: Z = 0 ist die **Frontseite**, +Z zeigt nach hinten, Y = 0 ist die flache Unterseite (Klebefläche). Die STL-Dateien liegen damit schon in Druckorientierung (Front nach unten). `Eye_L` sitzt bei +X und ist das Auge, das **für den Betrachter links** liegt.

### Parameter ändern

**Ändern → Parameter ändern.** Alle Tiefenmaße (Z: Extrusionen und Versatzebenen) reagieren sofort. Dazu gehören `front_t`, `eye_t`, `esp_front_wall`, `usb_overhang`, `usb_rear_gap`, `cover_t`, `lip_depth`, `led_seat_d`, `boss_len`, `pilot_depth`, `leg_depth` usw.

Die Umrissmaße (X/Y) berechnet das Skript. Dazu gehören `px`, Augen, LED-Position, ESP-Breite, Wandstärken und Lochpositionen. **Nach einer Änderung dieser Werte das Skript erneut ausführen, während das geänderte Design aktiv ist.** Es übernimmt alle Parameter-Ausdrücke aus dem aktiven Design und baut neue Dokumente.

Vorschau ohne Fusion: `python3 cad/preview/render_preview.py` (benötigt matplotlib) erzeugt `preview.png` mit denselben Maßen.

### Parameterliste (mm)

| Parameter | Default | Bedeutung |
|---|---|---|
| `px` | 3.75 | Pixel-Raster (16 px Gesamtbreite = 60 mm) |
| `body_w`, `body_h` | 12·px, 8·px | Körper ohne Arme (45 × 30) |
| `arm_len`, `arm_h`, `arm_y` | 2·px | Arm-Stummel (hohl, leuchten mit) |
| `leg_w`, `leg_len`, `leg_depth` | px, 2·px, 3 | Beinchen: Breite, Länge nach unten, Dicke (nur vordere Scheibe, massiv) |
| `leg_x_inner`, `leg_x_outer` | 2.5·px, 4.5·px | Bein-Mitten |
| `front_t` | 1.2 | Front-Diffusor (A) bzw. FrontPlate (B) |
| `wall`, `floor_t` | 2, 2.4 | Seiten/Decke, Boden |
| `rim_h`, `rim_w`, `rim_clr` | 1, 1, 0.15 | B: Zentrierrand hinten an der FrontPlate |
| `eye_w`, `eye_h`, `eye_cx`, `eye_cy` | px, 2·px, 3.5·px, 5·px | Augen |
| `eye_t` | front_t + 0.8 | Augen-Einleger-Tiefe |
| `LedPcbW`, `LedPcbL`, `LedPcbT`, `LedClr` | 10, 16.7, 2, 0.3 | LED-Streifenstück (60 LED/m) |
| `led_cx`, `led_cy` | 9.8, body_h/2 + 2 | LED-Mitte (Stücke liegen waagerecht) |
| `led_seat_d` | 0.4 | Vertiefung im Deckel für das LED-Stück |
| `wire_ch_w` | 3 | Kabelkanal im Deckel |
| `esp_l`, `esp_w`, `esp_pcb_t`, `esp_clr` | 22.52, 18, 1, 0.3 | ESP32-C3 Super Mini (Datenblatt) und Spiel |
| `esp_comp_h` | 3.3 | höchstes Bauteil (USB-C-Buchse) |
| `esp_front_wall` | 1.6 | Vorderwand der Bodentasche (= Anschlag) |
| `pad_relief_w`, `pad_free_end` | 1.5, 1.2 | Lötfreiraum neben den Pinreihen; padfreie Enden bleiben eng (X-Führung) |
| `recept_w`, `recept_h`, `recept_l` | 8.94, 3.26, 7.3 | USB-C-Buchse |
| `usb_c_h` | recept_h/2 | Buchsenmitte über Platinenoberseite |
| `usb_overhang` | 0.8 | Buchse steht über die Platinenkante (0,5–1) |
| `usb_out_gap` | 0 | Buchsenfront ↔ Deckel-**Außen**seite (0 = bündig) |
| `usb_clr` | 0.2 | Spiel um die Buchse je Seite |
| `usb_w`, `usb_h`, `usb_r` | recept + 2·usb_clr, usb_h/2 | USB-C-Loch (9,34 × 3,66, Stadion) |
| `slot_clr`, `slot_top` | 0.2, 0.6 | Schlitz im Deckel für die hintere Platinenkante: Spiel nach hinten, Höhe über Platine |
| `body_depth` | abgeleitet | front_t + esp_front_wall + esp_l + usb_overhang + usb_out_gap − cover_t |
| `cover_t`, `lip_depth`, `lip_w`, `lip_clr` | 2, 2, 1.6, 0.25 | Deckel und Zentrierrand |
| `boss`, `boss_len` | 5, 10 | Schraubdome in den 4 Ecken |
| `pilot_d`, `pilot_depth` | 1.7, 9 | Vorbohrung M2 (selbstschneidend) |
| `screw_clear_d`, `cbore_d`, `cbore_depth` | 2.3, 4.3, 1 | Durchgang und Senkung im Deckel |

## Aufbau des Modells

- **Leuchtkasten:** Der Innenraum ist komplett offen (auch die Arme) und hat keine Trennwände. Die 1,2 mm dünne Front ist der Diffusor. Die Beinchen sind massiv und leuchten deshalb nur schwach.
- **Augen** `Eye_L`/`Eye_R`: eigene Körper, bündig mit der Front, gehen durch die ganze Front und 0,8 mm tiefer. Sie bleiben vor dem Licht dunkel.
- **LEDs:** Beide Streifenstücke liegen **waagerecht** in 0,4 mm tiefen Vertiefungen auf der Innenseite des **Deckels**. Die Klebeseite klebt auf dem Deckel, die LEDs zeigen nach vorne. Bis zum Diffusor sind es 23,3 mm.
- **Kabelkanäle:** Zwei 3-mm-Rillen im Deckel führen von den äußeren LED-Enden nach unten zum ESP. Der Zentrierrand ist dort ausgespart.
- **ESP32-C3 Super Mini:** liegt in einer **Bodentasche** (18,6 × 22,52 mm, 1 mm tief), Bauteile nach oben, Platinenoberseite bündig mit dem Boden. USB-C zeigt nach hinten.
  - Die Vorderwand der Tasche ist der Anschlag. Das Einstecken des Kabels drückt die Platine dagegen.
  - Die hintere Platinenkante ragt 1,2 mm in einen **Schlitz in der Deckel-Innenseite** (18,6 × 1,8 mm, 1,4 mm tief). Dessen Boden begrenzt das Spiel nach hinten auf 0,2 mm. Dahinter bleibt 0,6 mm Deckelwand.
  - Die Buchse steckt im Deckel, ihre Front ist **bündig mit der Außenseite**. Der Stecker wird von außen eingesteckt, der Umspritzkörper liegt außen am Gehäuse an.
  - Neben den Pinreihen ist die Tasche je 1,5 mm breiter (Lötstellen, Drähte). Nur an den padfreien Enden (1,2 mm) führt die Tasche die Platine eng (±0,3 mm).
  - Die Außenseite des Bodens bleibt geschlossen (1,4 mm) und flach für das Klebeband.
- **USB-C-Loch:** exakt die Buchsenkontur plus 0,2 mm je Seite: **9,34 × 3,66 mm, Stadionform** (Radius 1,83 mm), konzentrisch zur Buchse (Mitte 4,03 mm über der Unterseite, in Fusion gemessen: Versatz 0,000 mm).
  - Das Loch ist **geschlossen**: Unter dem Loch bleiben 2,2 mm Material. Davon sind die unteren 1,2 mm volle 2 mm dick, der Rest 0,6 mm (dort liegt innen der Platinenschlitz).
- **BackCover:** Platte mit Umriss der Silhouette, Zentrierrand (an ESP, Kabelkanälen und Schraubdomen ausgespart), LED-Vertiefungen, Kabelrillen, Platinenschlitz, USB-C-Loch und **4 × M2 in Schraubdome in den Ecken** (5 × 5 mm, 10 mm lang, nur hinten, damit sie kaum Schatten werfen).
- **Variante B:** `FrontPlate` ist die weiße Front (Silhouette inkl. Beinchen, Vorderseite völlig flach) mit einem 1 mm hohen Zentrierrand hinten, der mit 0,15 mm Spiel in das `Housing` greift. Das `Housing` beginnt bei Z = 1,2 mm direkt hinter der Platte.

## Druckeinstellungen (Bambu Lab + AMS)

Allgemein: Orientierung **Front nach unten** (so exportiert, Z = 0 ist die Front). **Keine Stützstrukturen**, alle Innenformen sind Prismen in Druckrichtung. Schichthöhe 0,16–0,2 mm, Düse 0,4 mm, 3 Wandlinien, 15 % Infill. Glatte PEI-Platte für eine glatte Front.

**Wichtig für die Leuchtwirkung:** Die Front ist nur 1,2 mm dünn. Für den Diffusor 100 % Infill bzw. genug obere/untere Schichten, damit kein Infill-Muster durchscheint (die Front besteht bei 0,2 mm aus 6 Schichten, die alle als Boden-Schichten gedruckt werden).

### Variante A – Leuchtkasten (2 Farben)

1. In Bambu Studio `ClaudeBuddy_A_Lightbox.3mf` öffnen, oder `Body.stl`, `Eye_L.stl` und `Eye_R.stl` **gleichzeitig** importieren und die Frage „als ein Objekt mit mehreren Teilen laden?“ mit **Ja** beantworten. `BackCover` als eigenes Objekt drucken.
2. Filamente:
   - `Body`: **transluzentes Orange** (z. B. „PLA Translucent Orange“). Option ohne orangenes Filament: **weißes oder naturfarbenes (Natural) PLA**. Dann leuchtet die Front in der LED-Farbe, z. B. Claude-Orange per Firmware.
   - `Eye_L`, `Eye_R`: **Schwarz**.
3. Seitenwände (2 mm) aus transluzentem Filament leuchten etwas mit. Wer das nicht will, nimmt Variante B.

### Variante B – weiße Front + schwarzes Gehäuse (2 Farben)

1. `ClaudeBuddy_B_WhiteFront.3mf` öffnen, oder `FrontPlate.stl`, `Housing.stl`, `Eye_L.stl`, `Eye_R.stl` gleichzeitig als **ein Objekt mit mehreren Teilen** importieren. `BackCover` separat.
2. Filamente:
   - `FrontPlate`: **Weiß** (gern weiß-transluzent / Natural).
   - `Housing`, `Eye_L`, `Eye_R`: **Schwarz**.
   - Es bleiben also nur 2 Farben.
3. Gemeinsam gedruckt kommen zuerst die weißen Schichten der Platte (mit den schwarzen Augen darin), danach das schwarze Gehäuse darauf. Platte und Gehäuse verschmelzen dabei.
4. Alternativ getrennt drucken (Platte weiß, Housing schwarz, beide Front nach unten). Dann die Platte mit dem Zentrierrand in das Gehäuse stecken und mit wenig Sekundenkleber/UHU am Rand verkleben.
5. Optional Pergament-/Transparentpapier mit eigenem Gesicht aufkleben. Den 1:1-Umriss mit Augen gibt es als `export/B_whitefront/front_outline.dxf` (mm).

### BackCover (beide Varianten)

`BackCover.stl` separat laden und **um 180° kippen**, sodass die Außenfläche auf der Platte liegt und Zentrierrand, Platinenschlitz und LED-Vertiefungen nach oben zeigen („Auf Fläche legen“ → Außenfläche). Ohne Stützen drucken. A: Orange oder Schwarz (schwarz verhindert, dass Licht nach hinten austritt). B: Schwarz.

## Montage

**Benötigt:** 2 Stücke WS2812B-Streifen (60 LED/m, ohne Silikonschlauch, je 1 LED), ESP32-C3 Super Mini, dünne Litze (AWG 28–30, Silikon), etwas Heißkleber, 4 Schrauben M2.

1. **LED-Stücke** an den Schnittlinien trennen (10 × 16,7 mm). Die Pads liegen an den kurzen Enden.
2. **Verdrahtung (Kette, siehe CONTRACT.md):**
   - ESP `5V` → LED0 `5V`, ESP `GND` → LED0 `GND`, ESP `GPIO4` → LED0 `DIN`.
   - LED0 `DOUT`/`5V`/`GND` → LED1 `DIN`/`5V`/`GND`.
   - Pfeilrichtung auf dem Streifen beachten (DIN → DOUT).
   - Empfehlung: LED0 mit dem DIN-Ende **außen** einkleben, sodass die Zuleitung direkt in die Kabelrille nach unten läuft. Das DOUT-Ende liegt dann innen, direkt neben dem DIN-Ende von LED1 (2,3 mm Abstand, kurze Brücke).
   - LED0 ist das linke Auge **aus Sicht des Betrachters**. Bei Blick auf die Deckel-Innenseite liegt es **rechts**.
3. **LEDs einkleben:** Liner abziehen und das Stück in die Vertiefung auf der Deckel-Innenseite kleben, LED nach oben (= später nach vorne). Die Drähte in die Kabelrillen legen und mit einem Punkt Heißkleber fixieren.
4. **ESP:** Drähte an `5V`, `GND` und `GPIO4` von oben an die seitlichen Pads löten (Lötfreiraum 1,5 mm neben den Pinreihen). Den ESP mit Bauteilen nach oben und USB-C nach hinten in die Bodentasche legen und nach vorne gegen die Taschenwand schieben. Optional einen Punkt Heißkleber, aber nicht an die USB-Buchse.
5. Optional die rote Power-LED des ESP mit schwarzem Klebeband abkleben.
6. **Deckel aufsetzen.** Dabei die USB-Buchse in das Loch und die hintere Platinenkante in den Schlitz führen. 4 Schrauben in die Eckdome eindrehen, vorsichtig anziehen (PLA). Kabel einstecken.
7. **Monitor:** Doppelseitiges Klebeband auf die flache Unterseite kleben, hinter den Beinchen (ab 3 mm von der Front). Die Beinchen hängen vorne über die Monitorkante.

## Schrauben-Stückliste (BOM)

| Anz. | Teil | Hinweis |
|---|---|---|
| 4 | **M2 × 8 selbstschneidend** (für Kunststoff, Linsen- oder Zylinderkopf, Kopf-Ø ≤ 4 mm, z. B. ISO 7049 ST2,2 × 9,5) | in Ø 1,7-mm-Vorbohrung, 9 mm tief, in den Eckdomen. M2 × 6 geht auch. |
| – | Alternativ: M2 × 6 Zylinderkopf + M2-Gewindeeinsätze | dann `pilot_d` auf den Einsatz-Ø (≈ 3,2 mm) und ggf. `boss` auf 6 mm setzen. |

## Bekannte Restrisiken

- Der USB-Überstand der Buchse ist mit 0,8 mm angenommen (`usb_overhang`). Bei 0,5 mm liegt die Buchsenfront 0,3 mm hinter der Außenseite (unkritisch). Bei 1,0 mm steht sie 0,2 mm über (dann `usb_overhang` = 1,0 setzen und neu bauen). Vor dem Druck am echten Board nachmessen.
- Das USB-Loch hat nur 0,2 mm Spiel. Bei stark überextrudiertem Druck ggf. `usb_clr` auf 0,3 erhöhen.
- Die Unterseite des Super Mini wird als flach angenommen (nur Pads). Hat dein Board dort Bauteile, `esp_pcb_t`/`floor_t` anpassen.
- Ab 5050-LED bis Diffusor sind es 21,3 mm. Direkt vor den LEDs (neben den Augen) ist die Front etwas heller als in den Ecken.
