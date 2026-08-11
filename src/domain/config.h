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

  Rgb drlWhiteDay    = {255, 255, 255};
  Rgb drlWhiteNight  = {120, 120, 120};
  Rgb drlDimRedDay   = {120, 0, 0};
  Rgb drlDimRedNight = {60, 0, 0};
  Rgb indicatorOrange = {255, 80, 0};
  Rgb brakeRed        = {255, 0, 0};

  uint8_t denaliDay  = 50;
  uint8_t denaliLow  = 128;
  uint8_t denaliHigh = 255;
  uint8_t denaliSpot = 255;
};

Config defaultConfig();
FunctionMap& mapFor(Config& c, Function f);
const FunctionMap& mapFor(const Config& c, Function f);
