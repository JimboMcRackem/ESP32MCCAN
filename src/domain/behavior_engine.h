#pragma once
#include "domain/logical_state.h"
#include "domain/outputs.h"
#include "domain/config.h"
#include <cstdint>

// Tracks how long one indicator request has been continuously asserted.
struct IndTimer {
  bool     prev    = false;
  uint32_t sinceMs = 0;
};

struct EngineState {
  bool     spotLatched   = false;
  bool     flashPrev     = false;
  uint32_t flashRisingMs = 0;
  IndTimer leftTimer;
  IndTimer rightTimer;
};

OutputIntent computeOutputs(const LogicalState& s, const Config& cfg,
                            uint32_t nowMs, EngineState& est);
