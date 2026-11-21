#include "domain/test_mode.h"
#include <cstring>

namespace {

// Built through a constexpr helper rather than seven positional bools per
// row, which would be unreadable and easy to mis-review.
constexpr LogicalState mk(bool run, bool night, bool left, bool right,
                          bool brake, bool low, bool high) {
  LogicalState s{};
  s.run       = run;
  s.night     = night;
  s.leftInd   = left;
  s.rightInd  = right;
  s.rearBrake = brake;
  s.lowBeam   = low;
  s.highBeam  = high;
  return s;
}

// A night, low-beam state leaning `deg` (positive = right), for the cornering
// presets. It obeys the current settings like any scenario.
constexpr LogicalState leanNight(float deg) {
  LogicalState s = mk(true, true, false, false, false, true, false);
  s.leanDeg = deg;
  s.leanValid = true;
  s.speedKmh = 60.0f;      // above the default 40 km/h cornering gate
  s.speedValid = true;
  return s;
}

//                        run    night  left   right  brake  low    high
constexpr LogicalState kScenarios[] = {
  /* allOff     */ mk(false, false, false, false, false, false, false),
  /* drlDay     */ mk(true,  false, false, false, false, false, false),
  /* leftInd    */ mk(true,  false, true,  false, false, false, false),
  /* rightInd   */ mk(true,  false, false, true,  false, false, false),
  /* hazards    */ mk(true,  false, true,  true,  false, false, false),
  /* brake      */ mk(true,  false, false, false, true,  false, false),
  // lowBeam is the night preset: front white off, pods at low.
  /* lowBeam    */ mk(true,  true,  false, false, false, true,  false),
  /* highBeam   */ mk(true,  true,  false, false, false, false, true ),
  /* leanLeftNight  */ leanNight(-30.0f),
  /* leanRightNight */ leanNight(30.0f),
};

}  // namespace

// Index-aligned with kScenarios above. test_every_advertised_scenario_name
// _resolves is what keeps the two in step if either is edited.
const char* const kScenarioNames[] = {
  "allOff", "drlDay", "leftInd", "rightInd",
  "hazards", "brake", "lowBeam", "highBeam",
  "leanLeftNight", "leanRightNight",
};
const int kScenarioCount =
    (int)(sizeof(kScenarioNames) / sizeof(kScenarioNames[0]));

static_assert(sizeof(kScenarios) / sizeof(kScenarios[0]) ==
                  sizeof(kScenarioNames) / sizeof(kScenarioNames[0]),
              "kScenarios and kScenarioNames must stay index-aligned");

bool scenarioByName(const char* name, LogicalState& out) {
  if (!name || !*name) return false;
  for (int i = 0; i < kScenarioCount; ++i) {
    if (std::strcmp(name, kScenarioNames[i]) == 0) {
      out = kScenarios[i];
      return true;
    }
  }
  return false;
}

OutputIntent resolveOutputs(const LogicalState& real, const TestMode& t,
                            const Config& cfg, uint32_t nowMs,
                            EngineState& est, EngineState& testEst) {
  switch (t.kind) {
    case TestKind::Scenario:
      // A night scenario must show night even with DayNight unassigned.
      testEst.nightToggled = t.scenario.night;
      return computeOutputs(t.scenario, cfg, nowMs, testEst);
    case TestKind::Zones: {
      // The output walk lights a pod at the Low duty, never at Full.
      OutputIntent o = t.zones;
      o.auxDutyL = o.isOn(OUT_AUX_L) ? auxDutyFor(AuxLevel::Low, cfg) : 0;
      o.auxDutyR = o.isOn(OUT_AUX_R) ? auxDutyFor(AuxLevel::Low, cfg) : 0;
      return o;
    }
    case TestKind::Off:
    default:
      return computeOutputs(real, cfg, nowMs, est);
  }
}

bool testExpired(const TestMode& t, const Config& cfg, uint32_t nowMs) {
  if (t.kind == TestKind::Off) return false;
  return (nowMs - t.startedMs) >= cfg.testMaxMs;
}
