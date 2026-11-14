# Claude Buddy – Interface Contract (shared by all parts)

## Hardware
- MCU: ESP32-C3 Super Mini (18.00 x 22.52 mm PCB, pin rows 15.24 mm apart, USB-C centred on one short edge, slightly overhanging)
- 2x WS2812B ("NeoPixel"), chained: ESP GPIO 4 -> DIN LED0 (left eye) -> DOUT -> DIN LED1 (right eye)
- LED power: ESP "5V" pin (VBUS) -> both LED VDD; GND -> both LED GND
- LED form factor: single-LED pieces cut from a 60 LEDs/m WS2812B strip (~10 x 16.7 x 2 mm, pads at both short ends)
- Enclosure overall width ~60 mm (incl. arm nubs), USB-C exits at the back
- Whole front face is a light diffuser (light box); eyes are dark inserts (2nd color)
- LEDs mounted on the inside of the back cover, facing forward; ESP sits in a floor pocket
- Power only via USB-C (cable exits rear of enclosure)

## Network
- WiFi setup via WiFiManager captive portal, AP name "Claude-Buddy-Setup"
- mDNS hostname: claude-buddy  ->  http://claude-buddy.local  (port 80)

## Event transport
- Hooks send events over USB serial (one compact JSON line per event: session_id, hook_event_name,
  notification_type). WiFi/HTTP is used for the web UI; POST /hook still works as an alternative.

## HTTP API (device)
- POST /hook   body = raw Claude Code hook JSON from stdin (contains at least "session_id", "hook_event_name";
               Notification also "message", "notification_type" may exist). Response 200 {"ok":true}
- GET  /status -> JSON {"state":"idle|working|attention|done","sessions":[{"id":"…","state":"…","age_s":N}],"brightness":0-255}
- GET  /test?state=idle|working|attention|done  -> forces preview of that animation for 5 s
- GET  /brightness?value=0-255 -> sets & persists brightness
- GET  /  -> tiny HTML status page with test buttons and brightness slider

## Event -> session state mapping
- SessionStart                      -> idle (registers session)
- UserPromptSubmit, PreToolUse, PostToolUse, SubagentStop(*) -> working
- Notification, PermissionRequest   -> attention
  EXCEPT Notification with notification_type "idle_prompt" or "auth_success" -> ignore
  (idle_prompt fires ~60 s after every Stop and must NOT turn done into attention)
- Stop, StopFailure                 -> done
- SubagentStop on a session that is already done/idle -> ignore (late background subagents)
- SessionEnd                        -> remove session
(*) SubagentStop keeps parent working.
- Unknown events: ignore (200 OK).
- Timeouts: attention/working with no event for 15 min -> idle; any session silent 2 h -> removed;
  done -> after 10 min decays to idle.

## Aggregation (both eyes show the aggregate)
priority: attention > working > done > idle

## Animations
- idle: very dim warm white/orange slow breathing (~6 s period)
- working: Claude orange (#D97757 / approx RGB 217,119,87) smooth pulse ~1.5 s
- attention: fast blink orange/red-ish amber ~3 Hz (eye-catching)
- done: bright green flash x2, then steady soft green
- Occasional "blink" (both eyes off ~120 ms) every 4–10 s in idle/working/done
