#pragma once
#include <cstdint>

// Factory-reset button hold. Feed it the raw button level every loop pass.
class ResetHold {
 public:
  static constexpr uint32_t kHoldMs = 10000;
  static constexpr uint32_t kDebounceMs = 50;
  // True exactly once per completed hold.
  bool update(bool pressed, uint32_t nowMs);

 private:
  bool holding_ = false;
  bool fired_ = false;
  bool released_ = false;      // inside a release not yet long enough to count
  uint32_t start_ = 0;
  uint32_t releaseStart_ = 0;
};
