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
  // The generated phase starts at the request, so request at 0 first.
  Config cfg = defaultConfig();
  cfg.flashSource = FlashSource::Generate;
  EngineState est;
  LogicalState s; s.run = true; s.leftInd = true;
  computeOutputs(s, cfg, 0, est);
  TEST_ASSERT_EQUAL_UINT16(outMask(OUT_FR_DRL, OUT_RR_DRL),
                            computeOutputs(s, cfg, PHASE_OFF, est).on);
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

void test_brake_plus_left_indicator_dark_phase_keeps_the_rear_brake_dropped() {
  // The rear module ORs DRL and brake onto one light engine, so a brake left
  // asserted would light the indicating corner through the dark half and
  // destroy the flash contrast R48 requires. The generated phase starts at
  // the request, so request at 0 and sample the dark half at PHASE_OFF.
  Config cfg = defaultConfig();
  cfg.flashSource = FlashSource::Generate;
  EngineState est;
  LogicalState s; s.run = true; s.frontBrake = true; s.leftInd = true;
  computeOutputs(s, cfg, 0, est);
  TEST_ASSERT_EQUAL_UINT16(outMask(OUT_FR_DRL, OUT_RR_DRL, OUT_RR_BRK),
                            computeOutputs(s, cfg, PHASE_OFF, est).on);
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

void test_zero_blink_period_falls_back_to_340ms() {
  Config cfg = defaultConfig();
  cfg.blinkPeriodMs = 0;
  // Pin flashSource to Generate: see the comment on the dark-phase test above.
  cfg.flashSource = FlashSource::Generate;
  EngineState est;
  LogicalState s; s.run = true; s.leftInd = true;
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, 0, est).isOn(OUT_FL_IND));
  TEST_ASSERT_FALSE(computeOutputs(s, cfg, 400, est).isOn(OUT_FL_IND));
}

void test_follow_mirrors_the_bit_regardless_of_phase() {
  Config cfg = defaultConfig();
  cfg.flashSource = FlashSource::Follow;
  EngineState est;
  LogicalState s; s.run = true; s.leftInd = true;
  // Both sampled in what would be the generated dark half: follow ignores it.
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, PHASE_OFF, est).isOn(OUT_FL_IND));
  s.leftInd = false;
  TEST_ASSERT_FALSE(computeOutputs(s, cfg, PHASE_ON, est).isOn(OUT_FL_IND));
}

void test_generate_ignores_a_steady_bit_and_blinks() {
  Config cfg = defaultConfig();
  cfg.flashSource = FlashSource::Generate;
  EngineState est;
  LogicalState s; s.run = true; s.leftInd = true;
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, PHASE_ON, est).isOn(OUT_FL_IND));
  TEST_ASSERT_FALSE(computeOutputs(s, cfg, PHASE_OFF, est).isOn(OUT_FL_IND));
}

void test_auto_follows_a_toggling_bit() {
  Config cfg = defaultConfig();
  cfg.flashSource = FlashSource::Auto;
  EngineState est;
  LogicalState s; s.run = true; s.leftInd = true;
  // A toggling bit never stays true for 1.2 s, so auto stays in follow and
  // the lamp tracks the bit even in the generated dark half.
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, PHASE_OFF, est).isOn(OUT_FL_IND));
}

void test_auto_falls_back_to_generating_when_the_bit_sticks() {
  Config cfg = defaultConfig();
  cfg.flashSource = FlashSource::Auto;
  EngineState est;
  LogicalState s; s.run = true; s.leftInd = true;
  computeOutputs(s, cfg, 1000, est);            // rising edge at t=1000
  // Still inside the 1.2 s window: following.
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, 1000 + 400, est).isOn(OUT_FL_IND));
  // Past it: generating, and t=2600 lands in a dark half (2600 % 680 = 560).
  TEST_ASSERT_FALSE(computeOutputs(s, cfg, 2600, est).isOn(OUT_FL_IND));
}

void test_auto_restarts_its_window_on_each_rising_edge() {
  Config cfg = defaultConfig();
  cfg.flashSource = FlashSource::Auto;
  EngineState est;
  LogicalState s; s.run = true; s.leftInd = true;
  computeOutputs(s, cfg, 0, est);
  s.leftInd = false;
  computeOutputs(s, cfg, 2000, est);            // falling edge clears the hold
  s.leftInd = true;
  computeOutputs(s, cfg, 3000, est);            // new rising edge at t=3000
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, 3400, est).isOn(OUT_FL_IND));
}

void test_auto_watchdog_survives_millis_rollover() {
  Config cfg = defaultConfig();            // 1200 ms window, 340 ms blink
  cfg.flashSource = FlashSource::Auto;
  EngineState est;
  LogicalState s; s.run = true; s.leftInd = true;
  const uint32_t nearWrap = 0xFFFFFF00u;
  computeOutputs(s, cfg, nearWrap, est);   // rising edge, pre-wrap
  // 768 ms held: inside the window, so still following a (notionally) toggling
  // bit, and lit even though 0x200 % 680 == 512 is a generated dark half.
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, 0x200u, est).isOn(OUT_FL_IND));
  // 0x500 - 0xFFFFFF00 == 0x600 == 1536 ms held: past the window, so
  // generating. 1280 % 680 == 600 >= 340, so this is a dark half.
  TEST_ASSERT_FALSE(computeOutputs(s, cfg, 0x500u, est).isOn(OUT_FL_IND));
}

// The watchdog test's post-wrap samples catch a `nowMs > t.sinceMs` sanity
// guard, but NOT the other banned rollover form, `now >= then + threshold`:
// both forms answer "generate" at 0x200 and at 0x500. Only a PRE-wrap sample
// separates them, and only one whose generated phase is dark -- a pre-wrap
// sample in the lit half reads the same either way, which is why this test
// does not reuse the watchdog test's 0xFFFFFF00 (phase 0, so every pre-wrap
// offset lands in the lit half).
//
// 0xFFFFFB60 is 1184 ms short of the wrap, so `since + 1200` overflows to 16
// and the banned form compares against that. At since + 0x50 only 80 ms have
// elapsed, so Auto is still following and the lamp is lit; the banned form
// reads 0xFFFFFBB0 >= 16, falls through to generating, and
// 0xFFFFFBB0 % 680 == 512 >= 340 is a dark half, so it answers dark.
void test_auto_watchdog_does_not_fire_early_just_before_rollover() {
  Config cfg = defaultConfig();            // 1200 ms window, 340 ms blink
  cfg.flashSource = FlashSource::Auto;
  EngineState est;
  LogicalState s; s.run = true; s.leftInd = true;
  const uint32_t since = 0xFFFFFB60u;
  computeOutputs(s, cfg, since, est);      // rising edge, pre-wrap
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, since + 0x50u, est).isOn(OUT_FL_IND));
}

void test_generate_first_on_phase_is_full_from_any_start_time() {
  // 500 % 680 is a dark half under a free-running phase, so it must not matter.
  Config cfg = defaultConfig(); EngineState est;
  LogicalState s; s.run = true; s.leftInd = true;
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, 500, est).isOn(OUT_FL_IND));
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, 500 + 339, est).isOn(OUT_FL_IND));
  TEST_ASSERT_FALSE(computeOutputs(s, cfg, 500 + 340, est).isOn(OUT_FL_IND));
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, 500 + 680, est).isOn(OUT_FL_IND));
}

void test_reapplied_indicator_gets_a_new_full_on_phase() {
  Config cfg = defaultConfig(); EngineState est;
  LogicalState s; s.run = true; s.leftInd = true;
  computeOutputs(s, cfg, 0, est);
  s.leftInd = false; computeOutputs(s, cfg, 400, est);
  s.leftInd = true;                        // elapsed from 0 would be dark
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, 410, est).isOn(OUT_FL_IND));
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, 410 + 339, est).isOn(OUT_FL_IND));
}

void test_hazards_starting_one_tick_apart_stay_in_phase() {
  Config cfg = defaultConfig(); EngineState est;
  LogicalState s; s.run = true; s.leftInd = true;
  computeOutputs(s, cfg, 500, est);
  s.rightInd = true;
  computeOutputs(s, cfg, 510, est);
  OutputIntent o = computeOutputs(s, cfg, 500 + 345, est);  // both dark
  TEST_ASSERT_FALSE(o.isOn(OUT_FL_IND));
  TEST_ASSERT_FALSE(o.isOn(OUT_FR_IND));
  o = computeOutputs(s, cfg, 500 + 680, est);               // both lit
  TEST_ASSERT_TRUE(o.isOn(OUT_FL_IND));
  TEST_ASSERT_TRUE(o.isOn(OUT_FR_IND));
}

void test_adding_a_side_does_not_disturb_the_running_side() {
  Config cfg = defaultConfig(); EngineState est;
  LogicalState s; s.run = true; s.leftInd = true;
  computeOutputs(s, cfg, 0, est);
  s.rightInd = true;
  computeOutputs(s, cfg, 400, est);        // joins during the dark half
  TEST_ASSERT_FALSE(computeOutputs(s, cfg, 500, est).isOn(OUT_FL_IND));
  TEST_ASSERT_FALSE(computeOutputs(s, cfg, 500, est).isOn(OUT_FR_IND));
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, 680, est).isOn(OUT_FL_IND));
}

void test_generate_phase_survives_millis_rollover() {
  // Elapsed 768 -> lit. A free-running 0x200 % 680 == 512 would read dark.
  Config cfg = defaultConfig(); EngineState est;
  LogicalState s; s.run = true; s.leftInd = true;
  computeOutputs(s, cfg, 0xFFFFFF00u, est);
  TEST_ASSERT_TRUE(computeOutputs(s, cfg, 0x200u, est).isOn(OUT_FL_IND));
}

static Config mappedNight() {
  Config c = defaultConfig();
  mapFor(c, Function::DayNight).count = 1;
  return c;
}
static void hold(LogicalState s, const Config& c, uint32_t from, uint32_t ms, EngineState& e) {
  for (uint32_t t = 0; t <= ms; t += 10) computeOutputs(s, c, from + t, e);
}
static int lvl(AuxLevel a) { return (int)a; }
static const int OFF = (int)AuxLevel::Off;
static const int LOW = (int)AuxLevel::Low;
static const int FULL = (int)AuxLevel::Full;

void test_night_drops_front_white_and_puts_pods_at_low() {
  Config c = mappedNight(); EngineState e;
  LogicalState s; s.run = true; s.night = true;
  OutputIntent o = computeOutputs(s, c, 0, e);
  TEST_ASSERT_EQUAL_UINT16(outMask(OUT_RL_DRL, OUT_RR_DRL), o.on);
  TEST_ASSERT_EQUAL_INT(LOW, lvl(o.auxL));
  TEST_ASSERT_EQUAL_INT(LOW, lvl(o.auxR));
}

void test_day_has_pods_off() {
  Config c = mappedNight(); EngineState e;
  LogicalState s; s.run = true;
  OutputIntent o = computeOutputs(s, c, 0, e);
  TEST_ASSERT_EQUAL_UINT16(outMask(OUT_FL_DRL, OUT_FR_DRL, OUT_RL_DRL, OUT_RR_DRL), o.on);
  TEST_ASSERT_EQUAL_INT(OFF, lvl(o.auxL));
  TEST_ASSERT_EQUAL_INT(OFF, lvl(o.auxR));
}

void test_high_beam_day_is_full_with_front_white() {
  Config c = defaultConfig(); EngineState e;
  LogicalState s; s.run = true; s.highBeam = true;
  OutputIntent o = computeOutputs(s, c, 0, e);
  TEST_ASSERT_EQUAL_UINT16(outMask(OUT_FL_DRL, OUT_FR_DRL, OUT_RL_DRL, OUT_RR_DRL,
                                   OUT_AUX_L, OUT_AUX_R), o.on);
  TEST_ASSERT_EQUAL_INT(FULL, lvl(o.auxL));
  TEST_ASSERT_EQUAL_INT(FULL, lvl(o.auxR));
}

void test_high_beam_night_is_full_without_front_white() {
  Config c = mappedNight(); EngineState e;
  LogicalState s; s.run = true; s.night = true; s.highBeam = true;
  OutputIntent o = computeOutputs(s, c, 0, e);
  TEST_ASSERT_EQUAL_UINT16(outMask(OUT_RL_DRL, OUT_RR_DRL, OUT_AUX_L, OUT_AUX_R), o.on);
  TEST_ASSERT_EQUAL_INT(FULL, lvl(o.auxL));
  TEST_ASSERT_EQUAL_INT(FULL, lvl(o.auxR));
}

void test_low_never_sets_an_aux_bit() {
  Config c = mappedNight(); EngineState e;
  LogicalState s; s.run = true; s.night = true;
  TEST_ASSERT_EQUAL_UINT16(0, computeOutputs(s, c, 0, e).on & outMask(OUT_AUX_L, OUT_AUX_R));
}

void test_night_indicator_shows_amber_only_and_pods_stay_low() {
  Config c = mappedNight(); EngineState e;
  LogicalState s; s.run = true; s.night = true; s.leftInd = true;
  OutputIntent o = computeOutputs(s, c, 0, e);
  TEST_ASSERT_EQUAL_UINT16(outMask(OUT_RR_DRL, OUT_FL_IND, OUT_RL_IND), o.on);
  TEST_ASSERT_EQUAL_INT(LOW, lvl(o.auxL));
  TEST_ASSERT_EQUAL_INT(LOW, lvl(o.auxR));
}

void test_run_clear_at_night_turns_pods_off() {
  Config c = mappedNight(); EngineState e;
  LogicalState s; s.night = true;
  OutputIntent o = computeOutputs(s, c, 0, e);
  TEST_ASSERT_EQUAL_INT(OFF, lvl(o.auxL));
  TEST_ASSERT_EQUAL_INT(OFF, lvl(o.auxR));
}

void test_short_flash_leaves_pods_alone() {
  Config c = defaultConfig(); EngineState e;
  LogicalState s; s.run = true; s.flash = true;
  OutputIntent o = computeOutputs(s, c, 0, e);
  TEST_ASSERT_EQUAL_UINT16(outMask(OUT_FL_DRL, OUT_FR_DRL, OUT_RL_DRL, OUT_RR_DRL), o.on);
  TEST_ASSERT_EQUAL_INT(OFF, lvl(o.auxL));
  TEST_ASSERT_EQUAL_INT(OFF, lvl(o.auxR));
}

void test_darken_turns_off_the_indicating_pod_only() {
  Config c = mappedNight(); c.auxDarkenOnIndicate = true; EngineState e;
  LogicalState s; s.run = true; s.night = true; s.leftInd = true;
  OutputIntent o = computeOutputs(s, c, 0, e);
  TEST_ASSERT_EQUAL_INT(OFF, lvl(o.auxL));
  TEST_ASSERT_EQUAL_INT(LOW, lvl(o.auxR));
}

void test_darken_follows_the_request_not_the_phase() {
  Config c = mappedNight(); c.auxDarkenOnIndicate = true; EngineState e;
  LogicalState s; s.run = true; s.night = true; s.leftInd = true;
  computeOutputs(s, c, 0, e);
  OutputIntent o = computeOutputs(s, c, 345, e);   // dark half of the flash
  TEST_ASSERT_FALSE(o.isOn(OUT_FL_IND));
  TEST_ASSERT_EQUAL_INT(OFF, lvl(o.auxL));
}

void test_darken_skips_hazards() {
  Config c = mappedNight(); c.auxDarkenOnIndicate = true; EngineState e;
  LogicalState s; s.run = true; s.night = true; s.leftInd = true; s.rightInd = true;
  OutputIntent o = computeOutputs(s, c, 0, e);
  TEST_ASSERT_EQUAL_INT(LOW, lvl(o.auxL));
  TEST_ASSERT_EQUAL_INT(LOW, lvl(o.auxR));
}

void test_darken_skips_high_beam() {
  Config c = mappedNight(); c.auxDarkenOnIndicate = true; EngineState e;
  LogicalState s; s.run = true; s.night = true; s.leftInd = true; s.highBeam = true;
  OutputIntent o = computeOutputs(s, c, 0, e);
  TEST_ASSERT_EQUAL_INT(FULL, lvl(o.auxL));
  TEST_ASSERT_EQUAL_INT(FULL, lvl(o.auxR));
}

void test_darken_is_off_by_default() {
  Config c = mappedNight(); EngineState e;
  TEST_ASSERT_FALSE(c.auxDarkenOnIndicate);
  LogicalState s; s.run = true; s.night = true; s.leftInd = true;
  OutputIntent o = computeOutputs(s, c, 0, e);
  TEST_ASSERT_EQUAL_INT(LOW, lvl(o.auxL));
  TEST_ASSERT_EQUAL_INT(LOW, lvl(o.auxR));
}

void test_long_flash_toggles_night_once_per_press() {
  Config c = defaultConfig(); EngineState e;
  LogicalState s; s.run = true; s.flash = true;
  hold(s, c, 0, 790, e);
  TEST_ASSERT_FALSE(e.nightToggled);
  hold(s, c, 800, 3000, e);                // still held: exactly one toggle
  TEST_ASSERT_TRUE(e.nightToggled);
  s.flash = false; computeOutputs(s, c, 4000, e);
  s.flash = true;  hold(s, c, 4010, 800, e);
  TEST_ASSERT_FALSE(e.nightToggled);
}

void test_toggle_sets_low_pods_on_the_same_tick() {
  Config c = defaultConfig(); EngineState e;
  LogicalState s; s.run = true; s.flash = true;
  computeOutputs(s, c, 0, e);
  TEST_ASSERT_EQUAL_INT(LOW, lvl(computeOutputs(s, c, 800, e).auxL));
}

void test_steady_high_beam_never_toggles() {
  // HighBeam = bit 6 AND bit 16, HighBeamFlash = bit 16: flash reads true too.
  Config c = defaultConfig(); EngineState e;
  LogicalState s; s.run = true; s.flash = true; s.highBeam = true;
  hold(s, c, 0, 120000, e);
  TEST_ASSERT_FALSE(e.nightToggled);
}

void test_high_beam_at_any_point_cancels_the_press() {
  Config c = defaultConfig(); EngineState e;
  LogicalState s; s.run = true; s.flash = true;
  hold(s, c, 0, 400, e);
  s.highBeam = true;  computeOutputs(s, c, 410, e);
  s.highBeam = false; hold(s, c, 420, 2000, e);  // flash never released
  TEST_ASSERT_FALSE(e.nightToggled);
}

void test_toggled_press_moving_to_high_beam_does_not_toggle_back() {
  Config c = defaultConfig(); EngineState e;
  LogicalState s; s.run = true; s.flash = true;
  hold(s, c, 0, 800, e);
  TEST_ASSERT_TRUE(e.nightToggled);
  s.highBeam = true; hold(s, c, 810, 2000, e);
  TEST_ASSERT_TRUE(e.nightToggled);
}

void test_mapped_daynight_ignores_the_long_press() {
  Config c = mappedNight(); EngineState e;
  LogicalState s; s.run = true; s.flash = true;
  hold(s, c, 0, 2000, e);
  TEST_ASSERT_FALSE(e.nightToggled);
  TEST_ASSERT_EQUAL_INT(OFF, lvl(computeOutputs(s, c, 2010, e).auxL));
}

void test_bus_dropout_restarts_the_press() {
  Config c = defaultConfig(); EngineState e;
  LogicalState s; s.run = true; s.flash = true;
  hold(s, c, 0, 700, e);
  computeOutputs(LogicalState{}, c, 710, e);  // stale bus reads all false
  hold(s, c, 720, 700, e);                    // 700 ms since the restart
  TEST_ASSERT_FALSE(e.nightToggled);
}

void test_zero_hold_falls_back_to_800ms() {
  Config c = defaultConfig(); c.nightHoldMs = 0; EngineState e;
  LogicalState s; s.run = true; s.flash = true;
  hold(s, c, 0, 790, e);
  TEST_ASSERT_FALSE(e.nightToggled);
  hold(s, c, 800, 0, e);
  TEST_ASSERT_TRUE(e.nightToggled);
}

void test_night_hold_survives_millis_rollover() {
  Config c = defaultConfig(); EngineState e;
  LogicalState s; s.run = true; s.flash = true;
  computeOutputs(s, c, 0xFFFFFF00u, e);
  // `now >= then + 800` compares with 0x220 and fires here, 16 ms in.
  computeOutputs(s, c, 0xFFFFFF10u, e);
  TEST_ASSERT_FALSE(e.nightToggled);
  computeOutputs(s, c, 0x200u, e);            // 768 ms
  TEST_ASSERT_FALSE(e.nightToggled);
  computeOutputs(s, c, 0x220u, e);            // 800 ms
  TEST_ASSERT_TRUE(e.nightToggled);
}

void test_hold_below_400ms_falls_back_to_800ms() {
  // A 100 ms hold (what an old config import produced) would let an ordinary
  // flash-to-pass toggle night mode and drop the daytime front light.
  Config c = defaultConfig(); c.nightHoldMs = 100; EngineState e;
  LogicalState s; s.run = true; s.flash = true;
  hold(s, c, 0, 790, e);
  TEST_ASSERT_FALSE(e.nightToggled);
  hold(s, c, 800, 0, e);
  TEST_ASSERT_TRUE(e.nightToggled);
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_night_drops_front_white_and_puts_pods_at_low);
  RUN_TEST(test_day_has_pods_off);
  RUN_TEST(test_high_beam_day_is_full_with_front_white);
  RUN_TEST(test_high_beam_night_is_full_without_front_white);
  RUN_TEST(test_low_never_sets_an_aux_bit);
  RUN_TEST(test_night_indicator_shows_amber_only_and_pods_stay_low);
  RUN_TEST(test_run_clear_at_night_turns_pods_off);
  RUN_TEST(test_short_flash_leaves_pods_alone);
  RUN_TEST(test_darken_turns_off_the_indicating_pod_only);
  RUN_TEST(test_darken_follows_the_request_not_the_phase);
  RUN_TEST(test_darken_skips_hazards);
  RUN_TEST(test_darken_skips_high_beam);
  RUN_TEST(test_darken_is_off_by_default);
  RUN_TEST(test_long_flash_toggles_night_once_per_press);
  RUN_TEST(test_toggle_sets_low_pods_on_the_same_tick);
  RUN_TEST(test_steady_high_beam_never_toggles);
  RUN_TEST(test_high_beam_at_any_point_cancels_the_press);
  RUN_TEST(test_toggled_press_moving_to_high_beam_does_not_toggle_back);
  RUN_TEST(test_mapped_daynight_ignores_the_long_press);
  RUN_TEST(test_bus_dropout_restarts_the_press);
  RUN_TEST(test_zero_hold_falls_back_to_800ms);
  RUN_TEST(test_hold_below_400ms_falls_back_to_800ms);
  RUN_TEST(test_night_hold_survives_millis_rollover);
  RUN_TEST(test_generate_first_on_phase_is_full_from_any_start_time);
  RUN_TEST(test_reapplied_indicator_gets_a_new_full_on_phase);
  RUN_TEST(test_hazards_starting_one_tick_apart_stay_in_phase);
  RUN_TEST(test_adding_a_side_does_not_disturb_the_running_side);
  RUN_TEST(test_generate_phase_survives_millis_rollover);
  RUN_TEST(test_default_lights_four_drl);
  RUN_TEST(test_left_indicator_drops_left_drl_and_flashes_both_left_corners);
  RUN_TEST(test_left_indicator_dark_phase_leaves_left_corners_fully_dark);
  RUN_TEST(test_right_indicator_mirrors_left);
  RUN_TEST(test_hazards_flash_all_four_and_kill_every_drl);
  RUN_TEST(test_brake_adds_both_rear_brakes_to_the_drls);
  RUN_TEST(test_rear_brake_also_counts_as_brake);
  RUN_TEST(test_brake_plus_left_indicator_kills_the_indicating_corners_brake);
  RUN_TEST(test_brake_plus_left_indicator_dark_phase_keeps_the_rear_brake_dropped);
  RUN_TEST(test_brake_plus_right_indicator_mirrors_it);
  RUN_TEST(test_brake_plus_hazards_is_indicators_only);
  RUN_TEST(test_run_clear_keeps_indicators_and_drops_everything_else);
  RUN_TEST(test_aux_follows_high_beam_and_is_gated_by_run);
  RUN_TEST(test_zero_blink_period_falls_back_to_340ms);
  RUN_TEST(test_follow_mirrors_the_bit_regardless_of_phase);
  RUN_TEST(test_generate_ignores_a_steady_bit_and_blinks);
  RUN_TEST(test_auto_follows_a_toggling_bit);
  RUN_TEST(test_auto_falls_back_to_generating_when_the_bit_sticks);
  RUN_TEST(test_auto_restarts_its_window_on_each_rising_edge);
  RUN_TEST(test_auto_watchdog_survives_millis_rollover);
  RUN_TEST(test_auto_watchdog_does_not_fire_early_just_before_rollover);
  return UNITY_END();
}
