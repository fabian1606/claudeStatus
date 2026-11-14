#pragma once
#include <Arduino.h>

// Persistent settings (NVS via Preferences)
namespace Settings {
uint8_t loadBrightness();
void saveBrightness(uint8_t b);
void loadAnims();   // into Leds::animTable(); falls back to defaults
void saveAnims();   // from Leds::animTable()
void clearAnims();  // forget saved animations
}  // namespace Settings
