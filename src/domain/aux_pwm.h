#pragma once
#include <cstdint>

// LEDC compare value for a percent duty at `bits` resolution. 100% maps to
// 1 << bits, the value LEDC holds permanently high; anything above 100 is
// treated as 100.
constexpr uint32_t ledcDutyFor(uint8_t percent, uint8_t bits) {
  return (uint32_t)(percent > 100 ? 100 : percent) * (1u << bits) / 100u;
}
