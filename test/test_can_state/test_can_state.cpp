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
  cs.update(0x102, data);
  TEST_ASSERT_TRUE(cs.getBit(0x102, 18));
  TEST_ASSERT_FALSE(cs.getBit(0x102, 17));
  TEST_ASSERT_FALSE(cs.getBit(0x400, 18));   // unseen id -> false
}

void test_single_bit_function_maps_to_state() {
  CanState cs;
  uint8_t data[8] = {0};
  setBit(data, 18);              // left indicator
  setBit(data, 21);              // front brake
  cs.update(0x102, data);
  LogicalState s = cs.evaluate(defaultConfig());
  TEST_ASSERT_TRUE(s.leftInd);
  TEST_ASSERT_FALSE(s.rightInd);
  TEST_ASSERT_TRUE(s.frontBrake);
  TEST_ASSERT_TRUE(s.brake());
}

void test_and_combine_needs_all_bits() {
  CanState cs;
  uint8_t data[8] = {0};
  setBit(data, 6);               // only one of the two high-beam bits
  cs.update(0x102, data);
  TEST_ASSERT_FALSE(cs.evaluate(defaultConfig()).highBeam);
  setBit(data, 16);              // now both bits 6 and 16
  cs.update(0x102, data);
  TEST_ASSERT_TRUE(cs.evaluate(defaultConfig()).highBeam);
}

void test_run_unassigned_is_true() {
  CanState cs;
  uint8_t data[8] = {0};
  cs.update(0x102, data);
  TEST_ASSERT_TRUE(cs.evaluate(defaultConfig()).run);  // Run unmapped -> true
}

void test_daynight_unassigned_is_false() {
  CanState cs;
  uint8_t data[8] = {0};
  cs.update(0x102, data);
  TEST_ASSERT_FALSE(cs.evaluate(defaultConfig()).night);
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
  cs.update(0x102, data);
  TEST_ASSERT_FALSE(cs.evaluate(cfg).frontBrake);   // neither bit -> false
  setBit(data, 22);
  cs.update(0x102, data);
  TEST_ASSERT_TRUE(cs.evaluate(cfg).frontBrake);    // OR -> any bit true
}

void test_getbit_out_of_range_is_false() {
  CanState cs;
  uint8_t data[8] = {0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF};
  cs.update(0x102, data);
  TEST_ASSERT_TRUE(cs.getBit(0x102, 63));    // last valid bit
  TEST_ASSERT_FALSE(cs.getBit(0x102, 64));   // out of range -> false, no OOB read
  TEST_ASSERT_FALSE(cs.getBit(0x102, 200));
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
  return UNITY_END();
}
