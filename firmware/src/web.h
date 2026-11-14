#pragma once
#include <Arduino.h>

// HTTP API (see CONTRACT.md): POST /hook, GET /status, /test, /brightness, /
namespace Web {
void begin();   // call once WiFi is connected (port 80 is used by the setup portal before)
void loop();
bool started();
}  // namespace Web

// Shared helpers (also used by the serial console)
String buildStatusJson();
