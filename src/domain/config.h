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

// A number carried in a CAN frame: value = raw * scale + offset. Bit numbering
// matches BitRef (bit n = byte n/8, bit n%8, LSB = 0). Intel: startBit is the
// value's LSB. Motorola (bigEndian): startBit is the value's MSB, DBC
// convention. length 0 = unmapped. Decoding lives in domain/can_signal.h.
struct NumSignal {
  uint32_t id = 0;
  uint8_t  startBit = 0;
  uint8_t  length = 0;      // 1..32; 0 = unmapped
  bool     bigEndian = false;
  bool     isSigned = false;
  float    scale = 1.0f;
  float    offset = 0.0f;
  bool mapped() const { return length >= 1 && length <= 32; }
};

// The pods' yellow brightness input runs at about 150 Hz (period ~6.6 ms,
// measured from Oxford's own dial on hardware/Oscilliscope/4.bmp, emarked
// spec 2.2.1). Matched so the pod sees what its own dial sends. A build
// constant, not a setting.
constexpr uint32_t kAuxPwmHz = 150;

struct Config {
  FunctionMap map[(size_t)Function::COUNT];

  uint32_t blinkPeriodMs = 340;   // on-time == off-time
  uint32_t nightHoldMs   = 800;   // flash long-press that toggles night mode
  FlashSource flashSource = FlashSource::Generate;
  uint32_t testMaxMs     = 600000;   // absolute cap on a test-mode session
  bool     auxOffOnIndicateHighBeam = false;   // on high beam, indicating side's pod off too
  uint8_t  auxLowDuty  = 15;    // night Low, % duty on yellow (Oxford's stage 1)
  uint8_t  auxFullDuty = 100;   // high-beam Full, % duty; also caps Low

  // High beam by speed: at or below hbSlowKmh the pods run at hbSlowDuty,
  // at or above hbFullKmh at auxFullDuty, a straight line between.
  bool     speedScaleEnable = false;
  uint16_t hbSlowKmh  = 20;
  uint16_t hbFullKmh  = 80;
  uint8_t  hbSlowDuty = 50;
  // Cornering: from leanStartDeg to leanFullDeg the inside pod rises toward
  // leanBoostDuty (night Low) or auxFullDuty (high beam), and the outside pod
  // falls toward leanDimDuty. Below leanMinKmh (or with no valid speed) there
  // is no cornering effect, so walking the bike or the side stand's tilt
  // changes nothing. leanMinKmh 0 = no speed needed.
  bool     leanEnable    = false;
  uint16_t leanMinKmh    = 40;
  uint8_t  leanStartDeg  = 10;
  uint8_t  leanFullDeg   = 30;
  uint8_t  leanBoostDuty = 60;
  uint8_t  leanDimDuty   = 5;

  NumSignal speedSignal;   // road speed, km/h; unmapped by default
  NumSignal leanSignal;    // lean angle, degrees, positive = leaning right
};

Config defaultConfig();
FunctionMap& mapFor(Config& c, Function f);
const FunctionMap& mapFor(const Config& c, Function f);
