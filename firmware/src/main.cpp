// Claude Buddy – ESP32-C3 Super Mini firmware
// Shows the aggregate status of Claude Code sessions on two WS2812B "eyes".
// Interface spec: ../CONTRACT.md

#include <Arduino.h>
#include <ESPmDNS.h>
#include <WiFi.h>
#include <WiFiManager.h>

#include "config.h"
#include "hook.h"
#include "leds.h"
#include "sessions.h"
#include "settings.h"
#include "web.h"

namespace {

// ---------------------------------------------------------------------------
// WiFi state machine (non-blocking so the LEDs keep animating)
// ---------------------------------------------------------------------------
WiFiManager wm;

enum class Net : uint8_t { Connecting, Portal, Online, Lost };
Net net = Net::Connecting;
uint32_t netSince = 0;
uint32_t lastReconnect = 0;

void startMdns() {
  MDNS.end();
  if (MDNS.begin(BUDDY_HOSTNAME)) {
    MDNS.addService("http", "tcp", HTTP_PORT);
    Serial.println("[net] mDNS: http://" BUDDY_HOSTNAME ".local/");
  } else {
    Serial.println("[net] mDNS start failed");
  }
}

void goOnline() {
  net = Net::Online;
  netSince = millis();
  WiFi.setSleep(false);  // no modem power-save: avoids 100+ ms latency spikes / dropped hook requests
  Leds::setNetMode(Leds::NetMode::Online);
  Serial.printf("[net] connected to \"%s\", IP %s, RSSI %d dBm\n", WiFi.SSID().c_str(),
                WiFi.localIP().toString().c_str(), WiFi.RSSI());
  Web::begin();
  startMdns();
}

void startConnect() {
  net = Net::Connecting;
  netSince = millis();
  Leds::setNetMode(Leds::NetMode::Connecting);
  WiFi.mode(WIFI_STA);
  WiFi.begin();  // saved credentials
  Serial.println("[net] connecting with saved credentials...");
}

void startPortal() {
  bool saved = wm.getWiFiIsSaved();
  // With saved credentials (e.g. router temporarily down) give up after a while and retry the
  // normal connection; without credentials keep the portal open forever.
  wm.setConfigPortalTimeout(saved ? PORTAL_TIMEOUT_S : 0);
  wm.startConfigPortal(BUDDY_AP_NAME);
  net = Net::Portal;
  netSince = millis();
  Leds::setNetMode(Leds::NetMode::Portal);
  Serial.println("[net] setup portal open: connect to WiFi \"" BUDDY_AP_NAME "\" -> http://192.168.4.1");
}

void netSetup() {
  WiFi.setHostname(BUDDY_HOSTNAME);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  wm.setDebugOutput(false);
  wm.setConfigPortalBlocking(false);
  wm.setHostname(BUDDY_HOSTNAME);
  wm.setTitle("Claude Buddy");
  wm.setConnectTimeout(20);
  if (wm.getWiFiIsSaved()) startConnect();
  else startPortal();
}

void netLoop(uint32_t now) {
  bool up = WiFi.status() == WL_CONNECTED;
  switch (net) {
    case Net::Connecting:
      if (up) goOnline();
      else if (now - netSince > WIFI_CONNECT_TIMEOUT_MS) {
        Serial.println("[net] connect timeout");
        startPortal();
      }
      break;
    case Net::Portal:
      if (wm.process() || (up && !wm.getConfigPortalActive())) {
        goOnline();
      } else if (!wm.getConfigPortalActive()) {
        Serial.println("[net] portal timeout, retrying saved WiFi");
        startConnect();
      }
      break;
    case Net::Online:
      if (!up) {
        net = Net::Lost;
        netSince = lastReconnect = now;
        Serial.println("[net] WiFi lost, reconnecting in background (LEDs keep showing status)");
      }
      break;
    case Net::Lost:
      if (up) {
        Serial.printf("[net] reconnected, IP %s\n", WiFi.localIP().toString().c_str());
        net = Net::Online;
        startMdns();
      } else if (now - lastReconnect > WIFI_RECONNECT_INTERVAL_MS) {
        lastReconnect = now;
        Serial.println("[net] reconnect attempt");
        WiFi.disconnect();
        WiFi.begin();
      }
      break;
  }
}

// ---------------------------------------------------------------------------
// BOOT button (GPIO9): hold 5 s -> erase WiFi credentials and restart
// ---------------------------------------------------------------------------
uint32_t btnDownSince = 0;
bool btnArmed = false;  // only arm after the button was seen released once (GPIO9 is a strap pin)

void buttonLoop(uint32_t now) {
  bool down = digitalRead(PIN_BOOT_BTN) == LOW;
  if (!down) {
    if (btnDownSince) Leds::setResetFeedback(0, false);
    btnDownSince = 0;
    btnArmed = true;
    return;
  }
  if (!btnArmed) return;
  if (!btnDownSince) {
    btnDownSince = now ? now : 1;
    Serial.println("[btn] BOOT pressed - hold 5 s to reset WiFi");
  }
  uint32_t held = now - btnDownSince;
  if (held >= WIFI_RESET_HOLD_MS) {
    Serial.println("[btn] resetting WiFi credentials and restarting...");
    Leds::setResetFeedback(1, true);
    uint32_t t0 = millis();
    while (millis() - t0 < 1200) {  // short red flicker as confirmation
      Leds::update(millis());
      delay(5);
    }
    wm.resetSettings();
    ESP.restart();
  } else if (held > 500) {
    Leds::setResetFeedback((float)(held - 500) / (WIFI_RESET_HOLD_MS - 500), false);
  }
}

// ---------------------------------------------------------------------------
// USB serial console: hook JSON lines + a few commands
// ---------------------------------------------------------------------------
char serialLine[SERIAL_LINE_MAX + 1];
size_t serialLen = 0;
bool serialOverflow = false;

void handleSerialLine(char* line, size_t len, bool truncated) {
  while (len && isspace((unsigned char)line[len - 1])) line[--len] = 0;
  while (len && isspace((unsigned char)*line)) { line++; len--; }
  if (!len) return;
  if (line[0] == '{') {
    processHookPayload(line, len, truncated, "serial");
    return;
  }
  if (!strcmp(line, "status")) {
    Serial.println(buildStatusJson());
  } else if (!strncmp(line, "test ", 5)) {
    BuddyState s;
    if (parseStateName(line + 5, s)) {
      Leds::preview(s, millis());
      Serial.printf("[serial] test preview: %s\n", stateName(s));
    } else {
      Serial.println("[serial] usage: test idle|working|attention|done");
    }
  } else if (!strncmp(line, "brightness ", 11)) {
    int v = constrain(atoi(line + 11), 0, 255);
    Leds::setBrightness(v);
    Settings::saveBrightness(v);
    Serial.printf("[serial] brightness=%d (saved)\n", v);
  } else if (!strcmp(line, "wifi")) {
    Serial.printf("[serial] WiFi status=%d SSID=\"%s\" IP=%s RSSI=%d\n", WiFi.status(), WiFi.SSID().c_str(),
                  WiFi.localIP().toString().c_str(), WiFi.RSSI());
  } else if (!strcmp(line, "reset-wifi")) {
    Serial.println("[serial] erasing WiFi credentials, restarting");
    wm.resetSettings();
    ESP.restart();
  } else if (!strcmp(line, "reboot")) {
    ESP.restart();
  } else {
    Serial.println("[serial] send hook JSON as one line, or: status | test <state> | brightness <0-255> | wifi | "
                   "reset-wifi | reboot");
  }
}

void serialLoop() {
  int budget = 2048;  // bound the work per loop iteration
  while (Serial.available() > 0 && budget-- > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (serialLen) {
        serialLine[serialLen] = 0;
        handleSerialLine(serialLine, serialLen, serialOverflow);
      }
      serialLen = 0;
      serialOverflow = false;
    } else if (serialLen < SERIAL_LINE_MAX) {
      serialLine[serialLen++] = c;
    } else {
      serialOverflow = true;  // keep the first part, use substring fallback
    }
  }
}

uint32_t lastTick = 0;
BuddyState lastAgg = BuddyState::Idle;

}  // namespace

void setup() {
  Serial.begin(115200);
  Serial.setTxTimeoutMs(0);  // never block if no USB host is listening
  pinMode(PIN_BOOT_BTN, INPUT_PULLUP);
  randomSeed(esp_random());

  Settings::loadAnims();
  Leds::begin(Settings::loadBrightness());
  Serial.printf("\n[boot] Claude Buddy - brightness %u\n", Leds::brightness());
  netSetup();
}

void loop() {
  uint32_t now = millis();

  netLoop(now);
  Web::loop();
  serialLoop();
  buttonLoop(now);

  if (now - lastTick >= 1000) {
    lastTick = now;
    Sessions::tick(now);
  }
  BuddyState agg = Sessions::aggregate();
  if (agg != lastAgg) {
    Serial.printf("[state] %s -> %s (%u session(s))\n", stateName(lastAgg), stateName(agg),
                  (unsigned)Sessions::count());
    lastAgg = agg;
  }
  Leds::setState(agg);
  Leds::update(now);

  delay(1);  // yield to WiFi/idle task
}
