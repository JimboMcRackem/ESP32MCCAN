#pragma once
#include "domain/logical_state.h"
#include "domain/outputs.h"
#include "domain/config.h"
#include <cstdint>

// Tracks how long one indicator request has been continuously asserted.
struct IndTimer {
  bool     prev    = false;
  uint32_t sinceMs = 0;
};

struct EngineState {
  bool     nightToggled  = false;   // night mode from the flash long press
  bool     pressUsed     = false;   // this flash press has toggled or met high beam
  bool     flashPrev     = false;
  uint32_t flashRisingMs = 0;
  IndTimer leftTimer;
  IndTimer rightTimer;
  uint32_t flashAnchorMs = 0;   // generated phase starts here (see computeOutputs)

  // Pod brightness smoothing: each side's duty as last driven, and when.
  float    dutyL = 0, dutyR = 0;
  // Each pod's level on the last tick. Smoothing runs only while a pod stays
  // at the same level; any level change (on, off, Low <-> Full) is instant.
  AuxLevel prevL = AuxLevel::Off, prevR = AuxLevel::Off;
  uint32_t dutyMs = 0;
  bool     dutyInit = false;             // false until the first tick
};

// Fastest a lit pod's duty may move, in percent per second, so a pod glides
// into and out of a corner, and with speed, instead of stepping. A full
// 0-100 swing takes 0.4 s. It smooths only changes within one level: a pod
// turning on or off, or switching between Low and Full, goes straight to its
// target, as it did before smoothing existed.
constexpr float kAuxSlewPctPerS = 250.0f;

OutputIntent computeOutputs(const LogicalState& s, const Config& cfg,
                            uint32_t nowMs, EngineState& est);

// Percent duty on the pods' yellow wire for a level: Off 0, Full auxFullDuty,
// Low auxLowDuty capped at auxFullDuty.
uint8_t auxDutyFor(AuxLevel level, const Config& cfg);

// How far into the cornering effect the bike is: 0 at or below leanStartDeg
// of lean either way, 1 at or beyond leanFullDeg, a straight line between.
// 0 when cornering is off, the lean reading is invalid, or (leanMinKmh > 0)
// speed is invalid or below leanMinKmh. A range with
// leanFullDeg <= leanStartDeg is a step at leanStartDeg.
float leanFactor(const LogicalState& s, const Config& cfg);

// One lit pod's target duty, in percent, before smoothing (spec 5.3). Base is
// Low's duty, or on Full the speed curve. The inside-of-the-lean pod rises
// toward the boost (leanBoostDuty on Low, auxFullDuty on Full) and never
// falls below base; the outside pod falls toward leanDimDuty and never rises
// above base. Everything is capped at auxFullDuty. Off is 0.
float auxTargetDuty(AuxLevel level, bool insideOfLean, bool outsideOfLean,
                    float k, const LogicalState& s, const Config& cfg);
