#pragma once
#include "domain/gamma_table.h"
#include <cstdint>

struct Rgb { uint8_t r = 0, g = 0, b = 0; };

inline bool operator==(const Rgb& a, const Rgb& b) { return a.r==b.r && a.g==b.g && a.b==b.b; }
inline bool operator!=(const Rgb& a, const Rgb& b) { return !(a == b); }

// A colour split into a normalized hue (brightest channel is 255) and a
// separate perceptual level. Gamma applies to the LEVEL ONLY — applying it
// per channel would shift the hue of every non-neutral colour, which is
// exactly what this split exists to prevent.
struct ColorLevel {
  Rgb     hue   = {255, 255, 255};
  uint8_t level = 255;            // 0-255; shown in the UI as 0-100%
};

inline bool operator==(const ColorLevel& a, const ColorLevel& b) {
  return a.hue == b.hue && a.level == b.level;
}
inline bool operator!=(const ColorLevel& a, const ColorLevel& b) { return !(a == b); }

// hue * gamma8(level) / 255, per channel. The result is PWM duty.
inline Rgb resolveColor(const ColorLevel& c) {
  const int g = kGammaEncode[c.level];
  return Rgb{ (uint8_t)((c.hue.r * g) / 255),
              (uint8_t)((c.hue.g * g) / 255),
              (uint8_t)((c.hue.b * g) / 255) };
}

// Inverse, used to migrate configs written before the split. Duty-preserving:
//   resolveColor(colorFromRgb(x)) == x   for every colour this project ships.
inline ColorLevel colorFromRgb(const Rgb& c) {
  const uint8_t m = c.r > c.g ? (c.r > c.b ? c.r : c.b)
                              : (c.g > c.b ? c.g : c.b);
  if (m == 0) return ColorLevel{ Rgb{255, 255, 255}, 0 };
  return ColorLevel{ Rgb{ (uint8_t)((c.r * 255 + m / 2) / m),
                          (uint8_t)((c.g * 255 + m / 2) / m),
                          (uint8_t)((c.b * 255 + m / 2) / m) },
                     kGammaDecode[m] };
}
