#include "domain/reset_hold.h"

bool ResetHold::update(bool pressed, uint32_t nowMs) {
  if (!pressed) {
    if (!released_) { released_ = true; releaseStart_ = nowMs; }
    if (holding_ && nowMs - releaseStart_ >= kDebounceMs) { holding_ = false; fired_ = false; }
    return false;
  }
  if (released_) {
    // A release that lasted long enough ends the hold; shorter is bounce.
    if (holding_ && nowMs - releaseStart_ >= kDebounceMs) { holding_ = false; fired_ = false; }
    released_ = false;
  }
  if (!holding_) { holding_ = true; fired_ = false; start_ = nowMs; }
  if (!fired_ && nowMs - start_ >= kHoldMs) { fired_ = true; return true; }
  return false;
}
