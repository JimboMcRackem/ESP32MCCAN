#pragma once
#include <cstdint>
#include "domain/outputs.h"
#include "domain/reset_sequence.h"

// Factory-reset gesture feedback, shown on the four indicators now that the
// status LED's GPIO drives the pods' PWM (night-mode spec 6.1). Armed blinks
// them at 10 Hz, Confirmed holds them on; Idle and Cancelled change nothing.
// Only the indicator bits are touched.
OutputIntent withResetFeedback(OutputIntent o, ResetPhase phase, uint32_t nowMs);
