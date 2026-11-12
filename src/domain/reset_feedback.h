#pragma once
#include <cstdint>
#include "domain/outputs.h"
#include "domain/reset_sequence.h"

// Factory-reset gesture feedback, shown on the four indicators now that the
// status LED's GPIO drives the pods' PWM (night-mode spec 6.1). Only while
// parked (bus stale or kickstand down, the restart's own gate): a wet button
// read as held while riding must never mask or freeze a real turn signal
// (spec 2026-10-19 5.6, lamps keep working). Parked, Armed blinks them at
// 10 Hz and Confirmed holds them on; Idle and Cancelled change nothing. Only
// the indicator bits are touched.
OutputIntent withResetFeedback(OutputIntent o, bool parked, ResetPhase phase,
                               uint32_t nowMs);
