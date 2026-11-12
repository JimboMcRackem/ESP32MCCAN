#pragma once
#include <cstdint>

// One bit per physical output. This order is the harness order; it is mirrored
// by kOutputPins in the GPIO HAL and by the web app's test tab, so it must not
// be reordered without changing both.
enum OutputIndex : uint8_t {
  OUT_FL_DRL = 0, OUT_FL_IND,
  OUT_FR_DRL,     OUT_FR_IND,
  OUT_RL_DRL,     OUT_RL_IND, OUT_RL_BRK,
  OUT_RR_DRL,     OUT_RR_IND, OUT_RR_BRK,
  OUT_AUX_L,      OUT_AUX_R,
  OUT_COUNT   // = 12
};

// Aux pod brightness. A pod that is not Off is powered by its switch; its main
// LEDs then run at the duty on its yellow wire (night-mode spec 6.1).
enum class AuxLevel : uint8_t { Off, Low, Full };

// `on` is the whole switched state the HAL drives, one word on purpose, so a
// test asserts it in a single comparison and fails when an output nobody
// considered is also energised. An aux bit is set whenever that pod is not
// Off. `auxDuty` is the one shared yellow duty, in percent: every pod that is
// not Off carries the same level, so one duty serves both.
struct OutputIntent {
  uint16_t on = 0;
  AuxLevel auxL = AuxLevel::Off;
  AuxLevel auxR = AuxLevel::Off;
  uint8_t  auxDuty = 0;

  bool isOn(OutputIndex i) const { return ((on >> (uint8_t)i) & 1u) != 0u; }
  void set(OutputIndex i, bool v) {
    const uint16_t bit = (uint16_t)(1u << (uint8_t)i);
    if (v) on |= bit; else on &= (uint16_t)~bit;
  }
};

inline bool operator==(const OutputIntent& a, const OutputIntent& b) {
  return a.on == b.on && a.auxL == b.auxL && a.auxR == b.auxR &&
         a.auxDuty == b.auxDuty;
}
inline bool operator!=(const OutputIntent& a, const OutputIntent& b) { return !(a == b); }

// Mask literal helper, for expected values in tests and for presets.
// Precondition: every argument is a real output, i.e. < OUT_COUNT. The fold
// shifts by the raw value with no constraint, so outMask(OUT_COUNT) would
// yield bit 12 -- a bit no output has. Not checked: a runtime check does not
// belong in a constexpr helper, and nothing in production passes a value in.
constexpr uint16_t outMask() { return 0; }
template <typename... Rest>
constexpr uint16_t outMask(OutputIndex first, Rest... rest) {
  return (uint16_t)((1u << (uint8_t)first) | outMask(rest...));
}
