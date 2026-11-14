#include "hook.h"
#include <ArduinoJson.h>
#include "config.h"

namespace {

// Fallback: find "key" : "value" by plain substring search (used for truncated / malformed JSON).
// The first occurrence wins – in Claude Code payloads the top-level fields come before tool_input.
bool findStringField(const char* buf, size_t len, const char* key, char* out, size_t outLen) {
  size_t klen = strlen(key);
  for (size_t i = 0; i + klen + 2 <= len; i++) {
    if (buf[i] != '"' || memcmp(buf + i + 1, key, klen) != 0 || buf[i + 1 + klen] != '"') continue;
    size_t p = i + klen + 2;
    while (p < len && isspace((unsigned char)buf[p])) p++;
    if (p >= len || buf[p] != ':') continue;
    p++;
    while (p < len && isspace((unsigned char)buf[p])) p++;
    if (p >= len || buf[p] != '"') continue;
    p++;
    size_t o = 0;
    while (p < len && buf[p] != '"' && o + 1 < outLen) {
      if (buf[p] == '\\' && p + 1 < len) p++;  // naive unescape
      out[o++] = buf[p++];
    }
    out[o] = 0;
    return o > 0;
  }
  return false;
}

}  // namespace

EventResult processHookPayload(const char* buf, size_t len, bool truncated, const char* source) {
  char sessionId[SESSION_ID_LEN] = "";
  char event[40] = "";
  char ntype[40] = "";
  char message[96] = "";
  bool viaFallback = false;

  if (!truncated) {
    JsonDocument filter;
    filter["session_id"] = true;
    filter["hook_event_name"] = true;
    filter["notification_type"] = true;
    filter["message"] = true;

    JsonDocument doc;
    DeserializationError err =
        deserializeJson(doc, buf, len, DeserializationOption::Filter(filter), DeserializationOption::NestingLimit(32));
    if (!err) {
      strlcpy(sessionId, doc["session_id"] | "", sizeof(sessionId));
      strlcpy(event, doc["hook_event_name"] | "", sizeof(event));
      strlcpy(ntype, doc["notification_type"] | "", sizeof(ntype));
      strlcpy(message, doc["message"] | "", sizeof(message));
    } else {
      Serial.printf("[%s] JSON error: %s -> substring fallback\n", source, err.c_str());
    }
  }
  if (!*event) {
    viaFallback = true;
    findStringField(buf, len, "hook_event_name", event, sizeof(event));
    findStringField(buf, len, "session_id", sessionId, sizeof(sessionId));
    findStringField(buf, len, "notification_type", ntype, sizeof(ntype));
  }

  EventResult r = Sessions::handleEvent(sessionId, event, ntype, millis());
  Serial.printf("[%s] %s%s session=%s -> %s (%u B%s)", source, *event ? event : "<no event>",
                viaFallback ? " (fallback)" : "", *sessionId ? sessionId : "-",
                r == EventResult::Applied ? "applied" : r == EventResult::Removed ? "removed" : "ignored",
                (unsigned)len, truncated ? ", truncated" : "");
  if (*ntype) Serial.printf(" type=%s", ntype);
  if (*message) Serial.printf(" msg=\"%s\"", message);
  Serial.println();
  return r;
}
