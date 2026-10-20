#include "domain/reset_sequence.h"

ResetEvent ResetSequence::update(bool pressed, uint32_t nowMs) {
  if (phase_ == ResetPhase::Confirmed) return ResetEvent::None;

  // ResetHold sees every sample, so after an arm it fires again only once the
  // button has been released for kDebounceMs and held for a fresh 10 s.
  const bool fired = hold_.update(pressed, nowMs);

  if (phase_ != ResetPhase::Armed) {
    if (!fired) return ResetEvent::None;
    phase_ = ResetPhase::Armed;
    armedAt_ = nowMs;
    releasing_ = false;
    return ResetEvent::Armed;
  }

  // Armed. Unsigned differences throughout: wrap-safe.
  if (!pressed) {
    if (!releasing_) { releasing_ = true; releaseStart_ = nowMs; }
  } else {
    releasing_ = false;          // shorter than kDebounceMs: bounce, still held
  }
  const bool releaseInWindow =
      releasing_ && releaseStart_ - armedAt_ < kConfirmWindowMs;
  if (releaseInWindow && nowMs - releaseStart_ >= ResetHold::kDebounceMs) {
    phase_ = ResetPhase::Confirmed;
    return ResetEvent::Confirmed;
  }
  if (!releaseInWindow && nowMs - armedAt_ >= kConfirmWindowMs) {
    phase_ = ResetPhase::Cancelled;
    return ResetEvent::Cancelled;
  }
  return ResetEvent::None;
}
