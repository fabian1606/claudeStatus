#pragma once
// Claude Buddy – central configuration (see ../CONTRACT.md)

#include <Arduino.h>

// ---- Hardware ----
static constexpr uint8_t PIN_LEDS = 5;      // WS2812B chain (6 LEDs, all show the same state)
static constexpr uint8_t NUM_LEDS = 6;
static constexpr uint8_t PIN_BOOT_BTN = 9;  // BOOT button, active LOW

// ---- Network ----
#define BUDDY_AP_NAME "Claude-Buddy-Setup"
#define BUDDY_HOSTNAME "claude-buddy"
static constexpr uint16_t HTTP_PORT = 80;

// ---- Brightness ----
static constexpr uint8_t DEFAULT_BRIGHTNESS = 60;  // sits on a monitor -> moderate

// ---- Sessions ----
static constexpr size_t MAX_SESSIONS = 16;
static constexpr size_t SESSION_ID_LEN = 48;  // UUIDs are 36 chars

// ---- Timeouts (ms) ----
static constexpr uint32_t ACTIVE_TIMEOUT_MS = 15UL * 60UL * 1000UL;  // working/attention -> idle
static constexpr uint32_t DONE_DECAY_MS = 10UL * 60UL * 1000UL;      // done -> idle
static constexpr uint32_t SESSION_EXPIRE_MS = 2UL * 60UL * 60UL * 1000UL;  // silent -> removed
static constexpr uint32_t TEST_PREVIEW_MS = 5000;

// ---- WiFi ----
static constexpr uint32_t WIFI_CONNECT_TIMEOUT_MS = 20000;  // with saved creds, before portal opens
static constexpr uint32_t PORTAL_TIMEOUT_S = 180;           // portal timeout if creds are saved (then retry)
static constexpr uint32_t WIFI_RECONNECT_INTERVAL_MS = 30000;

// ---- Button ----
static constexpr uint32_t WIFI_RESET_HOLD_MS = 5000;

// ---- Body buffers ----
static constexpr size_t HTTP_BODY_MAX = 16 * 1024;   // bigger bodies: first 16 KB kept, rest discarded
static constexpr size_t SERIAL_LINE_MAX = 8 * 1024;
