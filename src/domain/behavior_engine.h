#pragma once
#include "domain/logical_state.h"
#include "domain/output_intent.h"
#include "domain/config.h"
#include <cstdint>

struct EngineState {
  bool spotLatched = false;
  bool flashPrev = false;
  uint32_t flashRisingMs = 0;
};

OutputIntent computeOutputs(const LogicalState& s, const Config& cfg,
                            uint32_t nowMs, EngineState& est);
