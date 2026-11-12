#include "domain/reset_feedback.h"

OutputIntent withResetFeedback(OutputIntent o, ResetPhase phase, uint32_t nowMs) {
  bool lit;
  switch (phase) {
    case ResetPhase::Armed:     lit = ((nowMs / 50) & 1u) == 0; break;   // 10 Hz
    case ResetPhase::Confirmed: lit = true; break;
    default:                    return o;
  }
  static const OutputIndex kInd[] = { OUT_FL_IND, OUT_FR_IND, OUT_RL_IND, OUT_RR_IND };
  for (OutputIndex i : kInd) o.set(i, lit);
  return o;
}
