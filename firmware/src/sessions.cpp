#include "sessions.h"

static Session table[MAX_SESSIONS];

const char* stateName(BuddyState s) {
  switch (s) {
    case BuddyState::Working: return "working";
    case BuddyState::Attention: return "attention";
    case BuddyState::Done: return "done";
    default: return "idle";
  }
}

bool parseStateName(const char* name, BuddyState& out) {
  if (!name) return false;
  if (!strcmp(name, "idle")) { out = BuddyState::Idle; return true; }
  if (!strcmp(name, "working")) { out = BuddyState::Working; return true; }
  if (!strcmp(name, "attention")) { out = BuddyState::Attention; return true; }
  if (!strcmp(name, "done")) { out = BuddyState::Done; return true; }
  return false;
}

namespace {

enum class Action : uint8_t { Unknown, ToIdle, ToWorking, ToAttention, ToDone, Remove };

Action mapEvent(const char* ev, const char* ntype) {
  if (!strcmp(ev, "SessionStart")) return Action::ToIdle;
  if (!strcmp(ev, "UserPromptSubmit") || !strcmp(ev, "PreToolUse") || !strcmp(ev, "PostToolUse") ||
      !strcmp(ev, "SubagentStop"))  // SubagentStop keeps parent working (see special case below)
    return Action::ToWorking;
  if (!strcmp(ev, "Notification")) {
    // idle_prompt fires ~60 s after every Stop and must not turn done into attention
    if (ntype && (!strcmp(ntype, "idle_prompt") || !strcmp(ntype, "auth_success"))) return Action::Unknown;
    return Action::ToAttention;  // permission_prompt, elicitation_dialog, missing type, ...
  }
  if (!strcmp(ev, "PermissionRequest")) return Action::ToAttention;
  if (!strcmp(ev, "Stop") || !strcmp(ev, "StopFailure")) return Action::ToDone;
  if (!strcmp(ev, "SessionEnd")) return Action::Remove;
  return Action::Unknown;
}

Session* find(const char* id) {
  for (auto& s : table)
    if (s.used && !strncmp(s.id, id, SESSION_ID_LEN - 1)) return &s;
  return nullptr;
}

Session* allocate(const char* id, uint32_t now) {
  Session* slot = nullptr;
  for (auto& s : table)
    if (!s.used) { slot = &s; break; }
  if (!slot) {  // full: evict the session with the oldest last event
    slot = &table[0];
    for (auto& s : table)
      if ((uint32_t)(now - s.lastEventMs) > (uint32_t)(now - slot->lastEventMs)) slot = &s;
    Serial.printf("[sess] table full, evicting %s\n", slot->id);
  }
  memset(slot, 0, sizeof(*slot));
  slot->used = true;
  strlcpy(slot->id, id, sizeof(slot->id));
  slot->state = BuddyState::Idle;
  slot->lastEventMs = now;
  slot->stateSinceMs = now;
  return slot;
}

void setState(Session& s, BuddyState st, uint32_t now) {
  if (s.state != st) s.stateSinceMs = now;
  s.state = st;
}

}  // namespace

namespace Sessions {

EventResult handleEvent(const char* sessionId, const char* eventName, const char* notificationType, uint32_t now) {
  if (!eventName || !*eventName) return EventResult::Ignored;
  Action a = mapEvent(eventName, notificationType);
  if (a == Action::Unknown) return EventResult::Ignored;
  if (!sessionId || !*sessionId) sessionId = "unknown";

  Session* s = find(sessionId);
  // Background subagents can finish after the parent's Stop: a SubagentStop on a session that is
  // already done/idle (or not known at all) must not switch it back to working.
  if (!strcmp(eventName, "SubagentStop") && (!s || s->state == BuddyState::Done || s->state == BuddyState::Idle))
    return EventResult::Ignored;
  if (a == Action::Remove) {
    if (s) s->used = false;
    return EventResult::Removed;
  }
  if (!s) s = allocate(sessionId, now);
  s->lastEventMs = now;
  switch (a) {
    case Action::ToIdle: setState(*s, BuddyState::Idle, now); break;
    case Action::ToWorking: setState(*s, BuddyState::Working, now); break;
    case Action::ToAttention: setState(*s, BuddyState::Attention, now); break;
    case Action::ToDone: setState(*s, BuddyState::Done, now); break;
    default: break;
  }
  return EventResult::Applied;
}

void tick(uint32_t now) {
  for (auto& s : table) {
    if (!s.used) continue;
    uint32_t silent = now - s.lastEventMs;
    if (silent >= SESSION_EXPIRE_MS) {
      Serial.printf("[sess] %s silent 2h -> removed\n", s.id);
      s.used = false;
      continue;
    }
    uint32_t inState = now - s.stateSinceMs;
    if ((s.state == BuddyState::Working || s.state == BuddyState::Attention) && silent >= ACTIVE_TIMEOUT_MS) {
      Serial.printf("[sess] %s %s timeout -> idle\n", s.id, stateName(s.state));
      setState(s, BuddyState::Idle, now);
    } else if (s.state == BuddyState::Done && inState >= DONE_DECAY_MS) {
      setState(s, BuddyState::Idle, now);
    }
  }
}

BuddyState aggregate() {
  BuddyState agg = BuddyState::Idle;
  for (auto& s : table)
    if (s.used && s.state > agg) agg = s.state;
  return agg;
}

size_t count() {
  size_t n = 0;
  for (auto& s : table) n += s.used;
  return n;
}

const Session* at(size_t i) {
  if (i >= MAX_SESSIONS || !table[i].used) return nullptr;
  return &table[i];
}

}  // namespace Sessions
