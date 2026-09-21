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

//                        run    night  left   right  brake  low    high
constexpr LogicalState kScenarios[] = {
  /* allOff     */ mk(false, false, false, false, false, false, false),
  /* drlDay     */ mk(true,  false, false, false, false, false, false),
  /* drlNight   */ mk(true,  true,  false, false, false, false, false),
  /* leftInd    */ mk(true,  false, true,  false, false, false, false),
  /* rightInd   */ mk(true,  false, false, true,  false, false, false),
  /* hazards    */ mk(true,  false, true,  true,  false, false, false),
  /* brake      */ mk(true,  false, false, false, true,  false, false),
  /* brakeNight */ mk(true,  true,  false, false, true,  false, false),
  /* lowBeam    */ mk(true,  true,  false, false, false, true,  false),
  /* highBeam   */ mk(true,  true,  false, false, false, false, true ),
};

}  // namespace

// Index-aligned with kScenarios above. test_every_advertised_scenario_name
// _resolves is what keeps the two in step if either is edited.
const char* const kScenarioNames[] = {
  "allOff", "drlDay", "drlNight", "leftInd", "rightInd",
  "hazards", "brake", "brakeNight", "lowBeam", "highBeam",
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
      return computeOutputs(t.scenario, cfg, nowMs, testEst);
    case TestKind::Zones:
      return t.zones;
    case TestKind::Off:
    default:
      return computeOutputs(real, cfg, nowMs, est);
  }
}

bool testExpired(const TestMode& t, const Config& cfg, uint32_t nowMs) {
  if (t.kind == TestKind::Off) return false;
  return (nowMs - t.startedMs) >= cfg.testMaxMs;
}
