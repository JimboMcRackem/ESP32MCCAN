#pragma once
#include <cstdint>

struct Rgb {
  uint8_t r = 0, g = 0, b = 0;
};

inline bool operator==(const Rgb& a, const Rgb& b) {
  return a.r == b.r && a.g == b.g && a.b == b.b;
}
inline bool operator!=(const Rgb& a, const Rgb& b) { return !(a == b); }
