#pragma once
#include <cstdint>
#include <cstddef>

enum class Function : uint8_t {
  Run, LeftInd, RightInd, FrontBrake, RearBrake,
  LowBeam, HighBeam, HighBeamFlash, DayNight, KickStand,
  COUNT
};

enum class Combine : uint8_t { Single, And, Or };

struct BitRef { uint32_t id = 0; uint8_t bit = 0; };

struct FunctionMap {
  Combine combine = Combine::Single;
  static constexpr uint8_t MAX_BITS = 4;
  BitRef bits[MAX_BITS];
  uint8_t count = 0;   // 0 = unassigned
};

// Where an indicator's on/off phase comes from. `Auto` mirrors the CAN bit's
// edges so our lamps flash in phase with the bike's own -- which added
// indicators are required to do -- and falls back to generating when the bit
// turns out to be a steady request flag rather than a flasher.
enum class FlashSource : uint8_t { Auto = 0, Follow, Generate };

// Longer than any legal flash period, so a bit still true after this is a
// steady flag, not a flasher.
constexpr uint32_t kFlashFollowTimeoutMs = 1200;

struct Config {
  FunctionMap map[(size_t)Function::COUNT];

  uint32_t blinkPeriodMs = 340;   // on-time == off-time
  uint32_t spotHoldMs    = 800;   // flash long-press threshold
  FlashSource flashSource = FlashSource::Auto;
  uint32_t testMaxMs     = 600000;   // absolute cap on a test-mode session
};

Config defaultConfig();
FunctionMap& mapFor(Config& c, Function f);
const FunctionMap& mapFor(const Config& c, Function f);
