#pragma once
#include <Arduino.h>
#include "sessions.h"

// Parse a raw Claude Code hook JSON payload (possibly truncated) and apply it to the session table.
// `source` is only used for logging ("http" / "serial").
EventResult processHookPayload(const char* buf, size_t len, bool truncated, const char* source);
