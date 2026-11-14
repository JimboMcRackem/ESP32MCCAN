#include <unity.h>
#include "domain/can_state.h"
#include "domain/config.h"

static void setBit(uint8_t data[8], uint8_t bit) {
  data[bit / 8] |= (uint8_t)(1u << (bit % 8));
}

void test_getbit_reads_lsb_first() {
  CanState cs;
  uint8_t data[8] = {0};
  setBit(data, 18);              // byte 2, bit 2
  cs.update(0x102, data, 0);
  TEST_ASSERT_TRUE(cs.getBit(0x102, 18));
  TEST_ASSERT_FALSE(cs.getBit(0x102, 17));
  TEST_ASSERT_FALSE(cs.getBit(0x400, 18));   // unseen id -> false
}

void test_single_bit_function_maps_to_state() {
  CanState cs;
  uint8_t data[8] = {0};
  setBit(data, 18);              // left indicator
  setBit(data, 21);              // front brake
  cs.update(0x102, data, 0);
  LogicalState s = cs.evaluate(defaultConfig(), 0);
  TEST_ASSERT_TRUE(s.leftInd);
  TEST_ASSERT_FALSE(s.rightInd);
  TEST_ASSERT_TRUE(s.frontBrake);
  TEST_ASSERT_TRUE(s.brake());
}

void test_and_combine_needs_all_bits() {
  CanState cs;
  uint8_t data[8] = {0};
  setBit(data, 6);               // only one of the two high-beam bits
  cs.update(0x102, data, 0);
  TEST_ASSERT_FALSE(cs.evaluate(defaultConfig(), 0).highBeam);
  setBit(data, 16);              // now both bits 6 and 16
  cs.update(0x102, data, 0);
  TEST_ASSERT_TRUE(cs.evaluate(defaultConfig(), 0).highBeam);
}

void test_run_unassigned_is_true() {
  CanState cs;
  uint8_t data[8] = {0};
  cs.update(0x102, data, 0);
  TEST_ASSERT_TRUE(cs.evaluate(defaultConfig(), 0).run);  // Run unmapped -> true
}

void test_daynight_unassigned_is_false() {
  CanState cs;
  uint8_t data[8] = {0};
  cs.update(0x102, data, 0);
  TEST_ASSERT_FALSE(cs.evaluate(defaultConfig(), 0).night);
}

void test_or_combine_needs_any_bit() {
  Config cfg = defaultConfig();
  FunctionMap fm;
  fm.combine = Combine::Or;
  fm.bits[0] = {0x102, 21};
  fm.bits[1] = {0x102, 22};
  fm.count = 2;
  mapFor(cfg, Function::FrontBrake) = fm;   // repurpose FrontBrake as an OR map for the test

  CanState cs;
  uint8_t data[8] = {0};
  cs.update(0x102, data, 0);
  TEST_ASSERT_FALSE(cs.evaluate(cfg, 0).frontBrake);   // neither bit -> false
  setBit(data, 22);
  cs.update(0x102, data, 0);
  TEST_ASSERT_TRUE(cs.evaluate(cfg, 0).frontBrake);    // OR -> any bit true
}

void test_getbit_out_of_range_is_false() {
  CanState cs;
  uint8_t data[8] = {0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF};
  cs.update(0x102, data, 0);
  TEST_ASSERT_TRUE(cs.getBit(0x102, 63));    // last valid bit
  TEST_ASSERT_FALSE(cs.getBit(0x102, 64));   // out of range -> false, no OOB read
  TEST_ASSERT_FALSE(cs.getBit(0x102, 200));
}

void test_a_fresh_state_is_stale_before_any_frame_arrives() {
  CanState cs;
  TEST_ASSERT_TRUE(cs.stale(0));
  TEST_ASSERT_TRUE(cs.stale(100000));
}

void test_a_frame_makes_it_fresh_then_it_goes_stale_at_500ms() {
  CanState cs;
  const uint8_t data[8] = {0};
  cs.update(0x102, data, 1000);
  TEST_ASSERT_FALSE(cs.stale(1000));
  TEST_ASSERT_FALSE(cs.stale(1499));
  TEST_ASSERT_TRUE(cs.stale(1500));
}

void test_evaluate_returns_all_false_when_stale() {
  // defaultConfig() already maps LeftInd to 0x102 bit 18, and this file
  // already has the setBit helper, so no hand-crafted byte layout is needed.
  CanState cs;
  uint8_t data[8] = {0};
  setBit(data, 18);
  cs.update(0x102, data, 1000);
  TEST_ASSERT_TRUE(cs.evaluate(defaultConfig(), 1000).leftInd);   // fresh
  TEST_ASSERT_FALSE(cs.evaluate(defaultConfig(), 1500).leftInd);  // stale
}

void test_stale_also_clears_the_unassigned_run_default() {
  // An unassigned Run normally evaluates TRUE so the bike works out of the box
  // (test_run_unassigned_is_true). Staleness must override even that, or a
  // quiet bus leaves the DRLs lit.
  CanState cs;
  const uint8_t data[8] = {0};
  cs.update(0x102, data, 1000);
  TEST_ASSERT_TRUE(cs.evaluate(defaultConfig(), 1000).run);
  TEST_ASSERT_FALSE(cs.evaluate(defaultConfig(), 1500).run);
}

void test_staleness_is_rollover_safe() {
  CanState cs;
  const uint8_t data[8] = {0};
  cs.update(0x102, data, 0xFFFFFF00u);
  // 0xFFFFFFF0 - 0xFFFFFF00 == 0xF0 == 240 ms: fresh.
  TEST_ASSERT_FALSE(cs.stale(0xFFFFFFF0u));
  // 0x100 - 0xFFFFFF00 == 0x200 == 512 ms, measured across the wrap: stale.
  TEST_ASSERT_TRUE(cs.stale(0x100u));
}

void setUp(void) {}
void tearDown(void) {}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_getbit_reads_lsb_first);
  RUN_TEST(test_single_bit_function_maps_to_state);
  RUN_TEST(test_and_combine_needs_all_bits);
  RUN_TEST(test_run_unassigned_is_true);
  RUN_TEST(test_daynight_unassigned_is_false);
  RUN_TEST(test_or_combine_needs_any_bit);
  RUN_TEST(test_getbit_out_of_range_is_false);
  RUN_TEST(test_a_fresh_state_is_stale_before_any_frame_arrives);
  RUN_TEST(test_a_frame_makes_it_fresh_then_it_goes_stale_at_500ms);
  RUN_TEST(test_evaluate_returns_all_false_when_stale);
  RUN_TEST(test_stale_also_clears_the_unassigned_run_default);
  RUN_TEST(test_staleness_is_rollover_safe);
  return UNITY_END();
}
