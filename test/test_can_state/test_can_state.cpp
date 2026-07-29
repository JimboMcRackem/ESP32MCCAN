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

void setUp(void) {}
void tearDown(void) {}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_getbit_reads_lsb_first);
  RUN_TEST(test_single_bit_function_maps_to_state);
  RUN_TEST(test_and_combine_needs_all_bits);
  RUN_TEST(test_run_unassigned_is_true);
  RUN_TEST(test_daynight_unassigned_is_false);
  return UNITY_END();
}
