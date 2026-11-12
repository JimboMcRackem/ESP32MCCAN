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

// Where an indicator's on/off phase comes from. `Generate` is the default
// because the board drives all four corners, so nothing has to stay in phase
// with the bike's own flasher. `Auto` mirrors the CAN bit's edges and falls
// back to generating when the bit turns out to be a steady request flag.
enum class FlashSource : uint8_t { Auto = 0, Follow, Generate };

// Longer than any legal flash period, so a bit still true after this is a
// steady flag, not a flasher.
constexpr uint32_t kFlashFollowTimeoutMs = 1200;

// Shortest night-mode hold the engine accepts. Anything shorter, including 0,
// is treated as the 800 ms default, so an ordinary flash-to-pass can never
// toggle night mode and drop the daytime front light.
constexpr uint32_t kMinNightHoldMs = 400;

// The pods' yellow brightness input runs at about 100 Hz (measured from
// Oxford's own dial, emarked spec 2.2.1). A build constant, not a setting.
constexpr uint32_t kAuxPwmHz = 100;

struct Config {
  FunctionMap map[(size_t)Function::COUNT];

  uint32_t blinkPeriodMs = 340;   // on-time == off-time
  uint32_t nightHoldMs   = 800;   // flash long-press that toggles night mode
  FlashSource flashSource = FlashSource::Generate;
  uint32_t testMaxMs     = 600000;   // absolute cap on a test-mode session
  bool     auxDarkenOnIndicate = false;   // indicating side's pod off at night
  uint8_t  auxLowDuty  = 15;    // night Low, % duty on yellow (Oxford's stage 1)
  uint8_t  auxFullDuty = 100;   // high-beam Full, % duty; also caps Low
};

Config defaultConfig();
FunctionMap& mapFor(Config& c, Function f);
const FunctionMap& mapFor(const Config& c, Function f);
