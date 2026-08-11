#pragma once
#include "domain/config.h"
#include "domain/logical_state.h"
#include <cstdint>

struct CanFrameSnapshot { uint32_t id; uint8_t data[8]; };

class CanState {
public:
  void update(uint32_t id, const uint8_t data[8]);
  bool getBit(uint32_t id, uint8_t bit) const;
  LogicalState evaluate(const Config& cfg) const;
  int snapshot(CanFrameSnapshot* out, int maxOut) const;

private:
  static constexpr int MAX_FRAMES = 16;
  struct Frame { uint32_t id = 0; uint8_t data[8] = {0}; bool seen = false; };
  Frame frames_[MAX_FRAMES];

  const Frame* find(uint32_t id) const;
  bool evalFunction(const FunctionMap& fm) const;
};
