#include "leds.h"
#include <Adafruit_NeoPixel.h>
#include <math.h>
#include "config.h"

namespace {

struct RGB {
  float r, g, b;
};

RGB scale(RGB c, float k) { return {c.r * k, c.g * k, c.b * k}; }
RGB lerp(RGB a, RGB b, float t) { return {a.r + (b.r - a.r) * t, a.g + (b.g - a.g) * t, a.b + (b.b - a.b) * t}; }

// Fixed colours (system feedback; state animations are configurable)
constexpr RGB C_ORANGE = {217, 119, 87};  // Claude orange #D97757
constexpr RGB C_BLUE = {0, 70, 255};      // network
constexpr RGB C_RED = {255, 0, 0};
constexpr RGB C_OFF = {0, 0, 0};

constexpr uint32_t STARTUP_FADE_MS = 1500;
constexpr uint32_t STARTUP_HOLD_MS = 600;
constexpr uint32_t CROSSFADE_MS = 300;
constexpr uint32_t BLINK_MS = 120;
constexpr uint32_t FRAME_MS = 16;

Adafruit_NeoPixel strip(NUM_LEDS, PIN_LEDS, NEO_GRB + NEO_KHZ800);

uint8_t gBrightness = DEFAULT_BRIGHTNESS;
BuddyState gAggregate = BuddyState::Idle;
BuddyState gPreviewState = BuddyState::Idle;
uint32_t gPreviewUntil = 0;
bool gPreviewOn = false;
Leds::NetMode gNet = Leds::NetMode::Connecting;
float gResetProgress = 0;
bool gResetConfirmed = false;

uint32_t gStartMs = 0;
bool gStartupDone = false;
uint32_t gLastFrame = 0;

int gScene = -1;
uint32_t gSceneStart = 0;
uint32_t gNextBlink = 0;
uint32_t gBlinkUntil = 0;

Leds::AnimCfg gAnims[Leds::NUM_STATES];
float gSpark[NUM_LEDS];
RGB gOut[NUM_LEDS];   // last frame shown (without eye blink)
RGB gFrom[NUM_LEDS];  // crossfade source

const char* const FX_NAMES[Leds::FX_COUNT] = {"solid", "breathe", "blink", "flash",
                                              "scanner", "wave", "rainbow", "sparkle",
                                              "flashoff", "off"};

float breathe(uint32_t t, uint32_t periodMs, float lo, float hi) {
  float ph = (float)(t % periodMs) / (float)periodMs;
  float s = 0.5f - 0.5f * cosf(ph * 2.0f * (float)M_PI);  // 0..1 smooth
  s = s * s * (3 - 2 * s);                                  // ease
  return lo + (hi - lo) * s;
}

RGB hsv(float h) {  // h 0..1, full saturation/value
  h = h - floorf(h);
  float x = h * 6.0f;
  int i = (int)x;
  float f = x - i;
  float q = 1 - f;
  switch (i % 6) {
    case 0: return {255, 255 * f, 0};
    case 1: return {255 * q, 255, 0};
    case 2: return {0, 255, 255 * f};
    case 3: return {0, 255 * q, 255};
    case 4: return {255 * f, 0, 255};
    default: return {255, 0, 255 * q};
  }
}

uint32_t periodOf(const Leds::AnimCfg& a) { return a.period < 100 ? 100 : a.period; }

bool isSnappy(BuddyState st, uint32_t inScene) {
  const Leds::AnimCfg& a = gAnims[(uint8_t)st];
  return a.effect == Leds::FX_BLINK ||
         ((a.effect == Leds::FX_FLASH || a.effect == Leds::FX_FLASH_OFF) && inScene < 2 * periodOf(a));
}

void sparkleTick(uint32_t P) {
  for (uint8_t i = 0; i < NUM_LEDS; i++) {
    gSpark[i] *= 0.88f;
    if ((uint32_t)random(0, 100000) < (uint32_t)(100000UL * FRAME_MS / P)) gSpark[i] = 1.0f;
  }
}

// Fills out[] with one animation frame for a state. blinkable = allow eye blink.
void stateFrame(BuddyState st, uint32_t now, uint32_t inScene, RGB* out, bool& blinkable) {
  const Leds::AnimCfg& a = gAnims[(uint8_t)st];
  RGB base = {(float)a.r, (float)a.g, (float)a.b};
  float lo = a.lo / 100.0f, hi = a.hi / 100.0f;
  uint32_t P = periodOf(a);
  blinkable = a.blink != 0;
  float ph = (float)(now % P) / (float)P;  // 0..1
  if (a.effect == Leds::FX_SPARKLE) sparkleTick(P);
  for (uint8_t i = 0; i < NUM_LEDS; i++) {
    float k = hi;
    RGB c = base;
    switch (a.effect) {
      case Leds::FX_SOLID: k = hi; break;
      case Leds::FX_BREATHE: k = breathe(now, P, lo, hi); break;
      case Leds::FX_BLINK: k = (inScene % P) < P * 55 / 100 ? hi : lo; break;
      case Leds::FX_FLASH:
        if (inScene < 2 * P) {
          k = (inScene % P) < P / 2 ? hi : 0;
          blinkable = false;
        } else {
          k = lo;
        }
        break;
      case Leds::FX_SCANNER: {
        float tri = ph < 0.5f ? ph * 2 : 2 - ph * 2;  // 0..1..0
        float pos = tri * (NUM_LEDS - 1);
        float d = fabsf((float)i - pos);
        float w = d >= 1.5f ? 0 : 1 - d / 1.5f;
        k = lo + (hi - lo) * w;
        break;
      }
      case Leds::FX_WAVE: {
        float x = ph - (float)i / NUM_LEDS;
        float w = 0.5f - 0.5f * cosf(x * 2.0f * (float)M_PI);
        k = lo + (hi - lo) * w;
        break;
      }
      case Leds::FX_RAINBOW:
        c = hsv(ph + (float)i / NUM_LEDS);
        k = hi;
        break;
      case Leds::FX_SPARKLE: k = lo + (hi - lo) * gSpark[i]; break;
      case Leds::FX_FLASH_OFF:
        k = (inScene < 2 * P && (inScene % P) < P / 2) ? hi : 0;
        blinkable = false;
        break;
      case Leds::FX_OFF:
        k = 0;
        blinkable = false;
        break;
    }
    out[i] = scale(c, k);
  }
}

void show(const RGB* c, bool record) {
  float k = gBrightness / 255.0f;
  auto ch = [k](float v) -> uint8_t {
    float o = v * k;
    if (o < 0) o = 0;
    if (o > 255) o = 255;
    return (uint8_t)(o + 0.5f);
  };
  for (uint8_t i = 0; i < NUM_LEDS; i++) {
    if (record) gOut[i] = c[i];
    strip.setPixelColor(i, strip.Color(ch(c[i].r), ch(c[i].g), ch(c[i].b)));
  }
  strip.show();
}

void showAll(RGB c) {
  RGB a[NUM_LEDS];
  for (uint8_t i = 0; i < NUM_LEDS; i++) a[i] = c;
  show(a, true);
}

uint8_t pct(int v) { return (uint8_t)constrain(v, 0, 100); }

}  // namespace

namespace Leds {

const char* effectName(uint8_t fx) { return fx < FX_COUNT ? FX_NAMES[fx] : "solid"; }

bool parseEffect(const char* name, uint8_t& out) {
  for (uint8_t i = 0; i < FX_COUNT; i++)
    if (!strcmp(name, FX_NAMES[i])) {
      out = i;
      return true;
    }
  return false;
}

AnimCfg defaultAnim(BuddyState s) {
  switch (s) {
    case BuddyState::Idle: return {FX_OFF, 255, 150, 70, 6000, 0, 0, 0};
    case BuddyState::Working: return {FX_WAVE, 217, 119, 87, 5400, 7, 28, 0};
    case BuddyState::Attention: return {FX_BREATHE, 255, 70, 0, 5150, 4, 100, 0};
    case BuddyState::Done: return {FX_FLASH_OFF, 30, 220, 70, 400, 0, 100, 0};
  }
  return {FX_SOLID, 255, 255, 255, 1000, 0, 50, 0};
}

void resetAnims() {
  for (uint8_t i = 0; i < NUM_STATES; i++) gAnims[i] = defaultAnim((BuddyState)i);
}

const AnimCfg& anim(BuddyState s) { return gAnims[(uint8_t)s]; }

void setAnim(BuddyState s, const AnimCfg& c) {
  AnimCfg v = c;
  if (v.effect >= FX_COUNT) v.effect = FX_SOLID;
  v.period = (uint16_t)constrain((int)v.period, 100, 20000);
  v.lo = pct(v.lo);
  v.hi = pct(v.hi);
  v.blink = v.blink ? 1 : 0;
  gAnims[(uint8_t)s] = v;
  if (gScene >= 0) gScene = -1;  // restart scene so one-shot effects replay
}

AnimCfg* animTable() { return gAnims; }

void begin(uint8_t b) {
  gBrightness = b;
  strip.begin();
  strip.clear();
  strip.show();
  gStartMs = millis();
  gNextBlink = gStartMs + random(4000, 10001);
}

void setBrightness(uint8_t b) { gBrightness = b; }
uint8_t brightness() { return gBrightness; }
void setState(BuddyState s) { gAggregate = s; }

void preview(BuddyState s, uint32_t now) {
  gPreviewState = s;
  gPreviewUntil = now + TEST_PREVIEW_MS;
  gPreviewOn = true;
  gScene = -1;  // force restart (e.g. done flash replays)
}

bool previewActive(uint32_t now) {
  if (gPreviewOn && (int32_t)(now - gPreviewUntil) >= 0) gPreviewOn = false;
  return gPreviewOn;
}

BuddyState previewState() { return gPreviewState; }

void setNetMode(NetMode m) { gNet = m; }

void setResetFeedback(float progress, bool confirmed) {
  gResetProgress = progress;
  gResetConfirmed = confirmed;
}

void update(uint32_t now) {
  if (now - gLastFrame < FRAME_MS) return;
  gLastFrame = now;

  // 1) startup fade-in (orange)
  if (!gStartupDone) {
    uint32_t t = now - gStartMs;
    if (t < STARTUP_FADE_MS) {
      float k = (float)t / STARTUP_FADE_MS;
      showAll(scale(C_ORANGE, k * k));
      return;
    }
    if (t < STARTUP_FADE_MS + STARTUP_HOLD_MS) {
      showAll(C_ORANGE);
      return;
    }
    gStartupDone = true;
  }

  // 2) BOOT-button feedback has top priority
  if (gResetConfirmed) {
    showAll((now / 100) % 2 ? C_RED : C_OFF);
    return;
  }
  if (gResetProgress > 0) {
    showAll(scale(C_RED, 0.1f + 0.9f * gResetProgress));
    return;
  }

  // 3) choose scene
  bool prev = previewActive(now);
  int scene;
  if (prev) scene = 10 + (int)gPreviewState;
  else if (gNet == NetMode::Portal) scene = 1;
  else if (gNet == NetMode::Connecting) scene = 2;
  else scene = 20 + (int)gAggregate;

  if (scene != gScene) {
    gScene = scene;
    gSceneStart = now;
    memcpy(gFrom, gOut, sizeof(gOut));
  }
  uint32_t inScene = now - gSceneStart;

  RGB target[NUM_LEDS];
  bool blinkable = false;
  bool snappy = false;
  if (scene == 1) {
    // WiFi setup portal: slow blue blink (1 s on / 1 s off)
    RGB c = ((now / 1000) % 2) ? scale(C_BLUE, 0.7f) : C_OFF;
    for (uint8_t i = 0; i < NUM_LEDS; i++) target[i] = c;
  } else if (scene == 2) {
    RGB c = scale(C_BLUE, breathe(now, 2000, 0.05f, 0.45f));
    for (uint8_t i = 0; i < NUM_LEDS; i++) target[i] = c;
  } else {
    BuddyState st = prev ? gPreviewState : gAggregate;
    stateFrame(st, now, inScene, target, blinkable);
    snappy = isSnappy(st, inScene);
  }

  // short crossfade between scenes (not for snappy effects like blink / flash)
  if (!snappy && inScene < CROSSFADE_MS) {
    float t = (float)inScene / CROSSFADE_MS;
    for (uint8_t i = 0; i < NUM_LEDS; i++) target[i] = lerp(gFrom[i], target[i], t);
  }

  // occasional eye blink
  if ((int32_t)(now - gNextBlink) >= 0) {
    if (blinkable) gBlinkUntil = now + BLINK_MS;
    gNextBlink = now + random(4000, 10001);
  }
  if (blinkable && (int32_t)(now - gBlinkUntil) < 0) {
    RGB off[NUM_LEDS];
    for (uint8_t i = 0; i < NUM_LEDS; i++) off[i] = C_OFF;
    memcpy(gOut, target, sizeof(gOut));  // keep real frame as fade source
    show(off, false);
    return;
  }
  show(target, true);
}

}  // namespace Leds
