#pragma once
#include "domain/logical_state.h"
#include "domain/outputs.h"
#include "domain/behavior_engine.h"
#include "domain/config.h"
#include <cstdint>

enum class TestKind : uint8_t { Off, Scenario, Zones };

// A held override of the lighting outputs. Single-holder, last-writer-wins:
// a second client taking it is not an error, and only the current owner's
// disconnect releases it.
struct TestMode {
  TestKind     kind      = TestKind::Off;
  LogicalState scenario;        // used when kind == Scenario
  OutputIntent zones;           // used when kind == Zones
  uint8_t      owner     = 0;   // WebSocket client id holding the mode
  uint32_t     startedMs = 0;
};

// Firmware-side scenario presets. This table is authoritative; the web app
// mirrors the names only for its buttons.
extern const char* const kScenarioNames[];
extern const int         kScenarioCount;

// Looks up a preset by name. Returns false for an unknown name and leaves
// `out` untouched — an unknown scenario must be an error, not a silent no-op.
bool scenarioByName(const char* name, LogicalState& out);

// The single seam between the behaviour engine and the PWM outputs.
//   Off      -> computeOutputs(real, ..., est)        exactly today's path
//   Scenario -> computeOutputs(t.scenario, ..., testEst)
//   Zones    -> t.zones verbatim
// Scenarios drive `testEst`, never `est`, so test mode is structurally unable
// to leave the real spot latch set after it exits.
OutputIntent resolveOutputs(const LogicalState& real, const TestMode& t,
                            const Config& cfg, uint32_t nowMs,
                            EngineState& est, EngineState& testEst);

// Absolute cap. Unsigned subtraction, so this is correct across millis()
// rollover. Always false when the mode is Off.
bool testExpired(const TestMode& t, const Config& cfg, uint32_t nowMs);
