#pragma once
#include <Arduino.h>
#include "sessions.h"

// Non-blocking eye animations, driven by millis(). Call Leds::update() every loop.
namespace Leds {

enum class NetMode : uint8_t { Online, Connecting, Portal };

// ---- configurable per-state animations (editable via web UI, stored in NVS) ----
enum Effect : uint8_t {
  FX_SOLID = 0,    // constant at "hi"
  FX_BREATHE,      // smooth lo..hi..lo
  FX_BLINK,        // hard on (hi) / off (lo)
  FX_FLASH,        // 2 flashes at hi, then steady at lo
  FX_SCANNER,      // bright dot sweeps back and forth over the LEDs
  FX_WAVE,         // brightness wave travelling along the LEDs
  FX_RAINBOW,      // colour wheel along the LEDs (ignores colour)
  FX_SPARKLE,      // random twinkling LEDs
  FX_FLASH_OFF,    // 2 flashes at hi, then off
  FX_OFF,          // LEDs off
  FX_COUNT
};
const char* effectName(uint8_t fx);  // "solid", "breathe", ...
bool parseEffect(const char* name, uint8_t& out);

struct AnimCfg {
  uint8_t effect;
  uint8_t r, g, b;
  uint16_t period;  // ms, 100..20000
  uint8_t lo, hi;   // percent 0..100
  uint8_t blink;    // occasional "eye blink" (1/0)
};
constexpr uint8_t NUM_STATES = 4;  // indexed by (uint8_t)BuddyState

const AnimCfg& anim(BuddyState s);
void setAnim(BuddyState s, const AnimCfg& c);  // clamps values
AnimCfg defaultAnim(BuddyState s);
void resetAnims();
// raw access for persistence
AnimCfg* animTable();

void begin(uint8_t brightness);
void setBrightness(uint8_t b);
uint8_t brightness();

void setState(BuddyState aggregate);           // aggregate of all sessions
void preview(BuddyState s, uint32_t now);      // forced preview for TEST_PREVIEW_MS
bool previewActive(uint32_t now);
BuddyState previewState();
void setNetMode(NetMode m);
// Button-hold feedback: progress 0..1 (0 = not held), confirmed = reset is happening.
void setResetFeedback(float progress, bool confirmed);

void update(uint32_t now);
}  // namespace Leds
