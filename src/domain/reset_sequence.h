#pragma once
#include <cstdint>
#include "domain/reset_hold.h"

// Factory-reset gesture on top of ResetHold: hold 10 s to arm, then RELEASE
// within kConfirmWindowMs to confirm. Still held when the window ends means a
// stuck or wet button: cancelled, and nothing more happens until the button
// has been released for kDebounceMs and a new full 10 s hold starts.
// Pure logic; feed it the raw button level every loop pass. It never blocks
// and never touches the lamps.
enum class ResetPhase : uint8_t { Idle, Armed, Cancelled, Confirmed };
enum class ResetEvent : uint8_t { None, Armed, Cancelled, Confirmed };

class ResetSequence {
 public:
  static constexpr uint32_t kConfirmWindowMs = 5000;
  // Returns the transition that happened on this sample, if any. Confirmed is
  // returned exactly once and is final.
  ResetEvent update(bool pressed, uint32_t nowMs);
  ResetPhase phase() const { return phase_; }

 private:
  ResetHold hold_;
  ResetPhase phase_ = ResetPhase::Idle;
  uint32_t armedAt_ = 0;
  bool releasing_ = false;     // a release is in progress (not yet debounced)
  uint32_t releaseStart_ = 0;
};
