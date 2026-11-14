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
  bool     nightToggled  = false;   // night mode from the flash long press
  bool     pressUsed     = false;   // this flash press has toggled or met high beam
  bool     flashPrev     = false;
  uint32_t flashRisingMs = 0;
  IndTimer leftTimer;
  IndTimer rightTimer;
  uint32_t flashAnchorMs = 0;   // generated phase starts here (see computeOutputs)
};

OutputIntent computeOutputs(const LogicalState& s, const Config& cfg,
                            uint32_t nowMs, EngineState& est);

// Percent duty on the pods' yellow wire for a level: Off 0, Full auxFullDuty,
// Low auxLowDuty capped at auxFullDuty.
uint8_t auxDutyFor(AuxLevel level, const Config& cfg);
