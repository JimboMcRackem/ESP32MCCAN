#pragma once
#include "domain/config.h"
#include "domain/logical_state.h"
#include <cstdint>

struct CanFrameSnapshot { uint32_t id; uint8_t data[8]; };

class CanState {
public:
  // No frame for this long and every logical input reads false. A quiet bus
  // means the bike's own lamps are off too, so holding the last frame's bits
  // would light our modules on data nobody is sending any more.
  static constexpr uint32_t kStaleMs = 500;

  void update(uint32_t id, const uint8_t data[8], uint32_t nowMs);
  bool getBit(uint32_t id, uint8_t bit) const;
  LogicalState evaluate(const Config& cfg, uint32_t nowMs) const;
  bool stale(uint32_t nowMs) const;
  int snapshot(CanFrameSnapshot* out, int maxOut) const;

private:
  static constexpr int MAX_FRAMES = 16;
  struct Frame { uint32_t id = 0; uint8_t data[8] = {0}; bool seen = false; };
  Frame frames_[MAX_FRAMES];

  bool     anyRx_    = false;   // false until the first frame ever arrives
  uint32_t lastRxMs_ = 0;

  const Frame* find(uint32_t id) const;
  bool evalFunction(const FunctionMap& fm) const;
};
