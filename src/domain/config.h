#pragma once
#include "domain/color.h"
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

struct Config {
  FunctionMap map[(size_t)Function::COUNT];

  uint32_t blinkPeriodMs = 340;   // on-time == off-time
  uint32_t spotHoldMs    = 800;   // flash long-press threshold

  // Levels are gamma-decoded from the duties this project shipped before the
  // hue/level split, so these defaults resolve to exactly the old values:
  // level 181 -> duty 120, level 132 -> duty 60.
  ColorLevel drlWhiteDay     = { {255, 255, 255}, 255 };
  ColorLevel drlWhiteNight   = { {255, 255, 255}, 181 };
  ColorLevel drlDimRedDay    = { {255, 0, 0},     181 };
  ColorLevel drlDimRedNight  = { {255, 0, 0},     132 };
  ColorLevel indicatorOrange = { {255, 80, 0},    255 };
  ColorLevel brakeRed        = { {255, 0, 0},     255 };

  // Denali stays raw duty: single-colour, already tuned against real beam
  // output, no hue to separate. Gamma here would silently re-level the beams.
  uint8_t denaliDay  = 50;
  uint8_t denaliLow  = 128;
  uint8_t denaliHigh = 255;
  uint8_t denaliSpot = 255;

  uint32_t testMaxMs = 600000;   // absolute cap on a test-mode session (10 min)
};

Config defaultConfig();
FunctionMap& mapFor(Config& c, Function f);
const FunctionMap& mapFor(const Config& c, Function f);
