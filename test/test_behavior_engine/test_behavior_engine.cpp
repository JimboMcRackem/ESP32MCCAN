#include <unity.h>
#include "domain/behavior_engine.h"

void setUp(void) {}
void tearDown(void) {}

// nowMs = 0 is inside the first ON half of the blink cycle, so a requested
// indicator reads as lit. PHASE_OFF lands in the dark half.
static const uint32_t PHASE_ON  = 0;
static const uint32_t PHASE_OFF = 400;   // > 340 ms, < 680 ms

static uint16_t run(LogicalState s, uint32_t nowMs) {
  Config cfg = defaultConfig();
  EngineState est;
  return computeOutputs(s, cfg, nowMs, est).on;
}

void test_default_lights_four_drl() {
  LogicalState s; s.run = true;
  TEST_ASSERT_EQUAL_UINT16(
    outMask(OUT_FL_DRL, OUT_FR_DRL, OUT_RL_DRL, OUT_RR_DRL),
    run(s, PHASE_ON));
}

void test_left_indicator_drops_left_drl_and_flashes_both_left_corners() {
  LogicalState s; s.run = true; s.leftInd = true;
  TEST_ASSERT_EQUAL_UINT16(
    outMask(OUT_FR_DRL, OUT_RR_DRL, OUT_FL_IND, OUT_RL_IND),
    run(s, PHASE_ON));
}

void test_left_indicator_dark_phase_leaves_left_corners_fully_dark() {
  LogicalState s; s.run = true; s.leftInd = true;
  TEST_ASSERT_EQUAL_UINT16(outMask(OUT_FR_DRL, OUT_RR_DRL), run(s, PHASE_OFF));
}

void test_right_indicator_mirrors_left() {
  LogicalState s; s.run = true; s.rightInd = true;
  TEST_ASSERT_EQUAL_UINT16(
    outMask(OUT_FL_DRL, OUT_RL_DRL, OUT_FR_IND, OUT_RR_IND),
    run(s, PHASE_ON));
}

void test_hazards_flash_all_four_and_kill_every_drl() {
  LogicalState s; s.run = true; s.leftInd = true; s.rightInd = true;
  TEST_ASSERT_EQUAL_UINT16(
    outMask(OUT_FL_IND, OUT_FR_IND, OUT_RL_IND, OUT_RR_IND),
    run(s, PHASE_ON));
}

void test_brake_adds_both_rear_brakes_to_the_drls() {
  LogicalState s; s.run = true; s.frontBrake = true;
  TEST_ASSERT_EQUAL_UINT16(
    outMask(OUT_FL_DRL, OUT_FR_DRL, OUT_RL_DRL, OUT_RR_DRL,
            OUT_RL_BRK, OUT_RR_BRK),
    run(s, PHASE_ON));
}

void test_rear_brake_also_counts_as_brake() {
  LogicalState s; s.run = true; s.rearBrake = true;
  TEST_ASSERT_TRUE((run(s, PHASE_ON) & outMask(OUT_RL_BRK, OUT_RR_BRK)) != 0);
}

void test_brake_plus_left_indicator_kills_the_indicating_corners_brake() {
  LogicalState s; s.run = true; s.frontBrake = true; s.leftInd = true;
  TEST_ASSERT_EQUAL_UINT16(
    outMask(OUT_FR_DRL, OUT_RR_DRL, OUT_RR_BRK, OUT_FL_IND, OUT_RL_IND),
    run(s, PHASE_ON));
}

void test_brake_plus_right_indicator_mirrors_it() {
  LogicalState s; s.run = true; s.rearBrake = true; s.rightInd = true;
  TEST_ASSERT_EQUAL_UINT16(
    outMask(OUT_FL_DRL, OUT_RL_DRL, OUT_RL_BRK, OUT_FR_IND, OUT_RR_IND),
    run(s, PHASE_ON));
}

void test_brake_plus_hazards_is_indicators_only() {
  LogicalState s;
  s.run = true; s.frontBrake = true; s.leftInd = true; s.rightInd = true;
  TEST_ASSERT_EQUAL_UINT16(
    outMask(OUT_FL_IND, OUT_FR_IND, OUT_RL_IND, OUT_RR_IND),
    run(s, PHASE_ON));
}

void test_run_clear_keeps_indicators_and_drops_everything_else() {
  LogicalState s; s.leftInd = true; s.frontBrake = true; s.highBeam = true;
  TEST_ASSERT_EQUAL_UINT16(outMask(OUT_FL_IND, OUT_RL_IND), run(s, PHASE_ON));
}

void test_aux_follows_high_beam_and_is_gated_by_run() {
  LogicalState s; s.run = true; s.highBeam = true;
  TEST_ASSERT_TRUE((run(s, PHASE_ON) & outMask(OUT_AUX_L, OUT_AUX_R))
                   == outMask(OUT_AUX_L, OUT_AUX_R));
  s.run = false;
  TEST_ASSERT_EQUAL_UINT16(0, run(s, PHASE_ON) & outMask(OUT_AUX_L, OUT_AUX_R));
}

void test_spot_latch_holds_aux_on_after_a_long_flash_press() {
  Config cfg = defaultConfig();
  EngineState est;
  LogicalState s; s.run = true; s.flash = true;
  computeOutputs(s, cfg, 0, est);                       // rising edge
  OutputIntent o = computeOutputs(s, cfg, cfg.spotHoldMs, est);
  TEST_ASSERT_TRUE(o.isOn(OUT_AUX_L));
  s.flash = false;
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, cfg.spotHoldMs + 50, est).isOn(OUT_AUX_L));
  s.lowBeam = true;                                     // auto-drop
  TEST_ASSERT_FALSE(computeOutputs(s, cfg, cfg.spotHoldMs + 100, est).isOn(OUT_AUX_L));
}

void test_zero_blink_period_falls_back_to_340ms() {
  Config cfg = defaultConfig();
  cfg.blinkPeriodMs = 0;
  EngineState est;
  LogicalState s; s.run = true; s.leftInd = true;
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, 0, est).isOn(OUT_FL_IND));
  TEST_ASSERT_FALSE(computeOutputs(s, cfg, 400, est).isOn(OUT_FL_IND));
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_default_lights_four_drl);
  RUN_TEST(test_left_indicator_drops_left_drl_and_flashes_both_left_corners);
  RUN_TEST(test_left_indicator_dark_phase_leaves_left_corners_fully_dark);
  RUN_TEST(test_right_indicator_mirrors_left);
  RUN_TEST(test_hazards_flash_all_four_and_kill_every_drl);
  RUN_TEST(test_brake_adds_both_rear_brakes_to_the_drls);
  RUN_TEST(test_rear_brake_also_counts_as_brake);
  RUN_TEST(test_brake_plus_left_indicator_kills_the_indicating_corners_brake);
  RUN_TEST(test_brake_plus_right_indicator_mirrors_it);
  RUN_TEST(test_brake_plus_hazards_is_indicators_only);
  RUN_TEST(test_run_clear_keeps_indicators_and_drops_everything_else);
  RUN_TEST(test_aux_follows_high_beam_and_is_gated_by_run);
  RUN_TEST(test_spot_latch_holds_aux_on_after_a_long_flash_press);
  RUN_TEST(test_zero_blink_period_falls_back_to_340ms);
  UNITY_END();
  return 0;
}
