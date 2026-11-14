#include "settings.h"
#include <Preferences.h>
#include "config.h"

namespace Settings {

uint8_t loadBrightness() {
  Preferences p;
  p.begin("buddy", true);
  uint8_t b = p.getUChar("bright", DEFAULT_BRIGHTNESS);
  p.end();
  return b;
}

void saveBrightness(uint8_t b) {
  Preferences p;
  p.begin("buddy", false);
  if (p.getUChar("bright", DEFAULT_BRIGHTNESS) != b || !p.isKey("bright")) p.putUChar("bright", b);
  p.end();
}

}  // namespace Settings

#include "leds.h"

namespace Settings {

static constexpr uint8_t ANIM_VERSION = 1;

void loadAnims() {
  Leds::resetAnims();
  Preferences p;
  p.begin("buddy", true);
  if (p.getUChar("animv", 0) == ANIM_VERSION &&
      p.getBytesLength("anims") == sizeof(Leds::AnimCfg) * Leds::NUM_STATES) {
    Leds::AnimCfg tmp[Leds::NUM_STATES];
    p.getBytes("anims", tmp, sizeof(tmp));
    for (uint8_t i = 0; i < Leds::NUM_STATES; i++) Leds::setAnim((BuddyState)i, tmp[i]);  // clamps
  }
  p.end();
}

void saveAnims() {
  Preferences p;
  p.begin("buddy", false);
  p.putBytes("anims", Leds::animTable(), sizeof(Leds::AnimCfg) * Leds::NUM_STATES);
  p.putUChar("animv", ANIM_VERSION);
  p.end();
}

void clearAnims() {
  Preferences p;
  p.begin("buddy", false);
  p.remove("anims");
  p.remove("animv");
  p.end();
}

}  // namespace Settings
