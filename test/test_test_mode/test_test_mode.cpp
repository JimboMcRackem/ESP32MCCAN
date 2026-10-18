#include <unity.h>
#include "domain/test_mode.h"

static Config cfg;
static EngineState est;
static EngineState testEst;

void setUp(void) {
  cfg = defaultConfig();
  est = EngineState{};
  testEst = EngineState{};
}
void tearDown(void) {}

// Time at which the blink phase is ON (nowMs % (2*period) < period).
static const uint32_t kOn = 0;

void test_off_passes_the_real_state_through(void) {
  LogicalState real; real.run = true;
  TestMode t;                                  // kind defaults to Off
  OutputIntent got  = resolveOutputs(real, t, cfg, kOn, est, testEst);
  EngineState ref;
  OutputIntent want = computeOutputs(real, cfg, kOn, ref);
  TEST_ASSERT_EQUAL_UINT16(want.on, got.on);
}

void test_scenario_ignores_the_real_state(void) {
  LogicalState real;                            // bike is off
  TestMode t;
  t.kind = TestKind::Scenario;
  TEST_ASSERT_TRUE(scenarioByName("brake", t.scenario));

  OutputIntent o = resolveOutputs(real, t, cfg, kOn, est, testEst);
  TEST_ASSERT_EQUAL_UINT16(
    outMask(OUT_FL_DRL, OUT_FR_DRL, OUT_RL_DRL, OUT_RR_DRL,
            OUT_RL_BRK, OUT_RR_BRK),
    o.on);
}

void test_scenario_blinks_at_the_configured_rate(void) {
  LogicalState real;
  TestMode t;
  t.kind = TestKind::Scenario;
  TEST_ASSERT_TRUE(scenarioByName("hazards", t.scenario));
  // Pin flashSource to Generate: this test exercises the generated blink
  // phase specifically. Under the default Auto, the scenario's indicator
  // request is freshly asserted (elapsed 0 < kFlashFollowTimeoutMs) and would
  // be followed lit through the second sample, masking the dark half this
  // test means to check.
  cfg.flashSource = FlashSource::Generate;

  // On-phase and off-phase of one blink cycle at the configured period.
  OutputIntent on  = resolveOutputs(real, t, cfg, 0, est, testEst);
  OutputIntent off = resolveOutputs(real, t, cfg, cfg.blinkPeriodMs, est, testEst);
  TEST_ASSERT_EQUAL_UINT16(
    outMask(OUT_FL_IND, OUT_FR_IND, OUT_RL_IND, OUT_RR_IND), on.on);
  TEST_ASSERT_EQUAL_UINT16(0, off.on);
}

void test_zones_pass_through_verbatim(void) {
  LogicalState real; real.run = true; real.rearBrake = true;
  TestMode t;
  t.kind = TestKind::Zones;
  t.zones.on = outMask(OUT_RL_BRK, OUT_AUX_L);

  OutputIntent o = resolveOutputs(real, t, cfg, kOn, est, testEst);
  TEST_ASSERT_EQUAL_UINT16(outMask(OUT_RL_BRK, OUT_AUX_L), o.on);
}

void test_a_stale_bus_does_not_disturb_a_held_test_session(void) {
  // CAN stale: every logical input reads false (Task 4's staleness rule).
  // A held zones override must survive that, or the lights drop out mid-test
  // for no reason the rider can see.
  TestMode t;
  t.kind = TestKind::Zones;
  t.zones.on = outMask(OUT_AUX_L, OUT_AUX_R);
  LogicalState stale;                           // bus-stale: all false
  OutputIntent o = resolveOutputs(stale, t, cfg, 5000, est, testEst);
  TEST_ASSERT_EQUAL_UINT16(outMask(OUT_AUX_L, OUT_AUX_R), o.on);
}

void test_scenario_cannot_corrupt_the_real_engine_state(void) {
  // A held 'flash' latches the spot lights. Run it as a scenario for well
  // past spotHoldMs and the REAL EngineState must be untouched, or exiting
  // test mode would leave the bike's spots latched on.
  LogicalState real;
  TestMode t;
  t.kind = TestKind::Scenario;
  t.scenario.run = true;
  t.scenario.flash = true;

  for (uint32_t ms = 0; ms <= cfg.spotHoldMs + 100; ms += 10) {
    resolveOutputs(real, t, cfg, ms, est, testEst);
  }
  TEST_ASSERT_TRUE_MESSAGE(testEst.spotLatched, "the test engine should latch");
  TEST_ASSERT_FALSE_MESSAGE(est.spotLatched, "the real engine must NOT latch");
  TEST_ASSERT_FALSE(est.flashPrev);
}

void test_expiry_is_false_when_off(void) {
  TestMode t;                                   // Off
  TEST_ASSERT_FALSE(testExpired(t, cfg, 0xFFFFFFFFu));
}

void test_expiry_at_the_cap(void) {
  TestMode t;
  t.kind = TestKind::Zones;
  t.startedMs = 1000;
  TEST_ASSERT_FALSE(testExpired(t, cfg, 1000 + cfg.testMaxMs - 1));
  TEST_ASSERT_TRUE(testExpired(t, cfg, 1000 + cfg.testMaxMs));
}

void test_expiry_survives_millis_rollover(void) {
  TestMode t;
  t.kind = TestKind::Zones;
  t.startedMs = 0xFFFFF000u;                    // ~4 s before rollover
  TEST_ASSERT_FALSE(testExpired(t, cfg, 0x00000100u));   // 4352 ms elapsed
  TEST_ASSERT_TRUE(testExpired(t, cfg, 0xFFFFF000u + cfg.testMaxMs));
}

void test_scenario_lookup_rejects_unknown_names(void) {
  LogicalState s;
  TEST_ASSERT_FALSE(scenarioByName("nope", s));
  TEST_ASSERT_FALSE(scenarioByName("", s));
}

void test_every_advertised_scenario_name_resolves(void) {
  // kScenarioNames is what the UI mirrors; a name in the list that does not
  // resolve would be a dead button.
  TEST_ASSERT_EQUAL_INT(10, kScenarioCount);
  LogicalState s;
  for (int i = 0; i < kScenarioCount; ++i) {
    TEST_ASSERT_TRUE_MESSAGE(scenarioByName(kScenarioNames[i], s),
                             "an advertised scenario name did not resolve");
  }
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_off_passes_the_real_state_through);
  RUN_TEST(test_scenario_ignores_the_real_state);
  RUN_TEST(test_scenario_blinks_at_the_configured_rate);
  RUN_TEST(test_zones_pass_through_verbatim);
  RUN_TEST(test_a_stale_bus_does_not_disturb_a_held_test_session);
  RUN_TEST(test_scenario_cannot_corrupt_the_real_engine_state);
  RUN_TEST(test_expiry_is_false_when_off);
  RUN_TEST(test_expiry_at_the_cap);
  RUN_TEST(test_expiry_survives_millis_rollover);
  RUN_TEST(test_scenario_lookup_rejects_unknown_names);
  RUN_TEST(test_every_advertised_scenario_name_resolves);
  return UNITY_END();
}
