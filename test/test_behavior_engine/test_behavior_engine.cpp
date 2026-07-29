#include <unity.h>
#include "domain/behavior_engine.h"
#include "domain/config.h"

static Config cfg;
static const Rgb OFF{0, 0, 0};

void setUp(void) { cfg = defaultConfig(); }
void tearDown(void) {}

// nowMs = 0 is within the "on" half of the blink cycle.
static uint32_t FLASH_ON = 0;
static uint32_t flashOffTime() { return cfg.blinkPeriodMs; }  // start of off-half

void test_drl_default_day() {
  LogicalState s; s.run = true;
  EngineState est{};
  OutputIntent o = computeOutputs(s, cfg, FLASH_ON, est);
  TEST_ASSERT_TRUE((o.frontL == cfg.drlWhiteDay));
  TEST_ASSERT_TRUE((o.frontR == cfg.drlWhiteDay));
  TEST_ASSERT_TRUE((o.rearL == cfg.drlDimRedDay));
  TEST_ASSERT_TRUE((o.rearR == cfg.drlDimRedDay));
}

void test_drl_default_night_uses_night_colors() {
  LogicalState s; s.run = true; s.night = true;
  EngineState est{};
  OutputIntent o = computeOutputs(s, cfg, FLASH_ON, est);
  TEST_ASSERT_TRUE((o.frontL == cfg.drlWhiteNight));
  TEST_ASSERT_TRUE((o.rearL == cfg.drlDimRedNight));
}

void test_left_indicator_flashes_left_corners_on_phase() {
  LogicalState s; s.run = true; s.leftInd = true;
  EngineState est{};
  OutputIntent o = computeOutputs(s, cfg, FLASH_ON, est);
  TEST_ASSERT_TRUE((o.frontL == cfg.indicatorOrange));
  TEST_ASSERT_TRUE((o.rearL == cfg.indicatorOrange));
  TEST_ASSERT_TRUE((o.frontR == cfg.drlWhiteDay));   // right side unaffected
  TEST_ASSERT_TRUE((o.rearR == cfg.drlDimRedDay));
}

void test_indicator_off_phase_is_fully_dark() {
  LogicalState s; s.run = true; s.leftInd = true;
  EngineState est{};
  OutputIntent o = computeOutputs(s, cfg, flashOffTime(), est);
  TEST_ASSERT_TRUE((o.frontL == OFF));
  TEST_ASSERT_TRUE((o.rearL == OFF));
}

void test_hazards_flash_all_four() {
  LogicalState s; s.run = true; s.leftInd = true; s.rightInd = true;
  EngineState est{};
  OutputIntent o = computeOutputs(s, cfg, FLASH_ON, est);
  TEST_ASSERT_TRUE((o.frontL == cfg.indicatorOrange));
  TEST_ASSERT_TRUE((o.frontR == cfg.indicatorOrange));
  TEST_ASSERT_TRUE((o.rearL == cfg.indicatorOrange));
  TEST_ASSERT_TRUE((o.rearR == cfg.indicatorOrange));
}

void test_brake_lights_both_rears_full_red() {
  LogicalState s; s.run = true; s.rearBrake = true;
  EngineState est{};
  OutputIntent o = computeOutputs(s, cfg, FLASH_ON, est);
  TEST_ASSERT_TRUE((o.rearL == cfg.brakeRed));
  TEST_ASSERT_TRUE((o.rearR == cfg.brakeRed));
  TEST_ASSERT_TRUE((o.frontL == cfg.drlWhiteDay));
}

void test_brake_plus_left_indicator_priority() {
  LogicalState s; s.run = true; s.frontBrake = true; s.leftInd = true;
  EngineState est{};
  OutputIntent o = computeOutputs(s, cfg, FLASH_ON, est);
  TEST_ASSERT_TRUE((o.rearL == cfg.indicatorOrange));  // indicator wins on left
  TEST_ASSERT_TRUE((o.rearR == cfg.brakeRed));         // right rear brakes
  TEST_ASSERT_TRUE((o.frontL == cfg.indicatorOrange));
  TEST_ASSERT_TRUE((o.frontR == cfg.drlWhiteDay));
}

void test_brake_plus_left_indicator_off_phase_left_is_dark() {
  LogicalState s; s.run = true; s.frontBrake = true; s.leftInd = true;
  EngineState est{};
  OutputIntent o = computeOutputs(s, cfg, flashOffTime(), est);
  TEST_ASSERT_TRUE((o.rearL == OFF));       // fully dark, brake suppressed
  TEST_ASSERT_TRUE((o.rearR == cfg.brakeRed));
}

void test_not_run_drl_off_but_indicator_works() {
  LogicalState s; s.run = false; s.leftInd = true;
  EngineState est{};
  OutputIntent on = computeOutputs(s, cfg, FLASH_ON, est);
  TEST_ASSERT_TRUE((on.frontL == cfg.indicatorOrange));
  TEST_ASSERT_TRUE((on.rearL == cfg.indicatorOrange));
  TEST_ASSERT_TRUE((on.frontR == OFF));     // non-indicating corners dark
  TEST_ASSERT_TRUE((on.rearR == OFF));
}

void test_not_run_brake_ignored() {
  LogicalState s; s.run = false; s.rearBrake = true;
  EngineState est{};
  OutputIntent o = computeOutputs(s, cfg, FLASH_ON, est);
  TEST_ASSERT_TRUE((o.rearL == OFF));
  TEST_ASSERT_TRUE((o.rearR == OFF));
}

void test_denali_off_when_not_run() {
  LogicalState s; s.run = false;
  EngineState est{};
  TEST_ASSERT_EQUAL_UINT8(0, computeOutputs(s, cfg, 0, est).denali);
}

void test_denali_daytime_level() {
  LogicalState s; s.run = true;              // day, no beams
  EngineState est{};
  TEST_ASSERT_EQUAL_UINT8(cfg.denaliDay, computeOutputs(s, cfg, 0, est).denali);
}

void test_denali_low_when_night_or_lowbeam() {
  LogicalState s; s.run = true; s.lowBeam = true;
  EngineState est{};
  TEST_ASSERT_EQUAL_UINT8(cfg.denaliLow, computeOutputs(s, cfg, 0, est).denali);
}

void test_denali_high_beam_level() {
  LogicalState s; s.run = true; s.highBeam = true;
  EngineState est{};
  TEST_ASSERT_EQUAL_UINT8(cfg.denaliHigh, computeOutputs(s, cfg, 0, est).denali);
}

void test_spot_latches_after_hold_then_persists() {
  cfg.denaliSpot = 200;   // distinct from denaliHigh (255) so the spot branch is observable
  LogicalState s; s.run = true; s.highBeam = true; s.flash = true;
  EngineState est{};
  // t=0 flash pressed (rising edge), not yet held long enough -> high-beam level, not latched
  TEST_ASSERT_EQUAL_UINT8(cfg.denaliHigh, computeOutputs(s, cfg, 0, est).denali);
  TEST_ASSERT_FALSE(est.spotLatched);
  // t=spotHoldMs: held long enough -> latches to spot level
  TEST_ASSERT_EQUAL_UINT8(cfg.denaliSpot,
                          computeOutputs(s, cfg, cfg.spotHoldMs, est).denali);
  TEST_ASSERT_TRUE(est.spotLatched);
  // release flash, still high beam -> spot stays latched
  s.flash = false;
  TEST_ASSERT_EQUAL_UINT8(cfg.denaliSpot,
                          computeOutputs(s, cfg, cfg.spotHoldMs + 500, est).denali);
  TEST_ASSERT_TRUE(est.spotLatched);
}

void test_spot_auto_drops_on_low_beam() {
  LogicalState s; s.run = true; s.highBeam = true; s.flash = true;
  EngineState est{};
  computeOutputs(s, cfg, 0, est);
  computeOutputs(s, cfg, cfg.spotHoldMs, est);       // latched
  TEST_ASSERT_TRUE(est.spotLatched);
  // rider selects low beam -> spot drops
  LogicalState low; low.run = true; low.lowBeam = true;
  OutputIntent o = computeOutputs(low, cfg, cfg.spotHoldMs + 100, est);
  TEST_ASSERT_FALSE(est.spotLatched);
  TEST_ASSERT_EQUAL_UINT8(cfg.denaliLow, o.denali);
}

void test_short_flash_press_does_not_latch() {
  LogicalState s; s.run = true; s.highBeam = true; s.flash = true;
  EngineState est{};
  computeOutputs(s, cfg, 0, est);                    // rising edge
  computeOutputs(s, cfg, cfg.spotHoldMs - 50, est);  // released early below
  s.flash = false;
  computeOutputs(s, cfg, cfg.spotHoldMs - 40, est);
  TEST_ASSERT_FALSE(est.spotLatched);
}

void test_denali_night_only_selects_low() {
  LogicalState s; s.run = true; s.night = true;   // night mode, low beam not set
  EngineState est{};
  TEST_ASSERT_EQUAL_UINT8(cfg.denaliLow, computeOutputs(s, cfg, 0, est).denali);
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_drl_default_day);
  RUN_TEST(test_drl_default_night_uses_night_colors);
  RUN_TEST(test_left_indicator_flashes_left_corners_on_phase);
  RUN_TEST(test_indicator_off_phase_is_fully_dark);
  RUN_TEST(test_hazards_flash_all_four);
  RUN_TEST(test_brake_lights_both_rears_full_red);
  RUN_TEST(test_brake_plus_left_indicator_priority);
  RUN_TEST(test_brake_plus_left_indicator_off_phase_left_is_dark);
  RUN_TEST(test_not_run_drl_off_but_indicator_works);
  RUN_TEST(test_not_run_brake_ignored);
  RUN_TEST(test_denali_off_when_not_run);
  RUN_TEST(test_denali_daytime_level);
  RUN_TEST(test_denali_low_when_night_or_lowbeam);
  RUN_TEST(test_denali_high_beam_level);
  RUN_TEST(test_spot_latches_after_hold_then_persists);
  RUN_TEST(test_spot_auto_drops_on_low_beam);
  RUN_TEST(test_short_flash_press_does_not_latch);
  RUN_TEST(test_denali_night_only_selects_low);
  return UNITY_END();
}
