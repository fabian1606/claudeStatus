#pragma once
#include <Arduino.h>
#include "config.h"

// Order matters: higher value = higher aggregation priority.
enum class BuddyState : uint8_t { Idle = 0, Done = 1, Working = 2, Attention = 3 };

const char* stateName(BuddyState s);
bool parseStateName(const char* name, BuddyState& out);

struct Session {
  bool used;
  char id[SESSION_ID_LEN];
  BuddyState state;
  uint32_t lastEventMs;   // any event for this session
  uint32_t stateSinceMs;  // when current state was entered
};

enum class EventResult : uint8_t { Applied, Removed, Ignored };

namespace Sessions {
// Apply a hook event. Unknown / filtered events -> Ignored (session table untouched).
// notificationType may be nullptr or "" (only relevant for "Notification").
EventResult handleEvent(const char* sessionId, const char* eventName, const char* notificationType, uint32_t now);
// Timeouts / expiry. Call regularly.
void tick(uint32_t now);
BuddyState aggregate();
size_t count();
// Iterate used slots: returns nullptr if slot i is empty.
const Session* at(size_t i);
}  // namespace Sessions
