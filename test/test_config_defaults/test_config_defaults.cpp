#include <unity.h>
#include "domain/config.h"

void test_default_timing_and_colors() {
  Config c = defaultConfig();
  TEST_ASSERT_EQUAL_UINT32(340, c.blinkPeriodMs);
  TEST_ASSERT_EQUAL_UINT32(800, c.spotHoldMs);
  TEST_ASSERT_TRUE((c.indicatorOrange == Rgb{255, 80, 0}));
}

void test_experia_indicator_mapping() {
  Config c = defaultConfig();
  const FunctionMap& left = mapFor(c, Function::LeftInd);
  TEST_ASSERT_EQUAL_UINT8(1, left.count);
  TEST_ASSERT_EQUAL_HEX32(0x102, left.bits[0].id);
  TEST_ASSERT_EQUAL_UINT8(18, left.bits[0].bit);
}

void test_experia_highbeam_is_and_of_two_bits() {
  Config c = defaultConfig();
  const FunctionMap& hb = mapFor(c, Function::HighBeam);
  TEST_ASSERT_EQUAL(Combine::And, hb.combine);
  TEST_ASSERT_EQUAL_UINT8(2, hb.count);
  TEST_ASSERT_EQUAL_UINT8(6, hb.bits[0].bit);
  TEST_ASSERT_EQUAL_UINT8(16, hb.bits[1].bit);
}

void test_run_and_daynight_unassigned() {
  Config c = defaultConfig();
  TEST_ASSERT_EQUAL_UINT8(0, mapFor(c, Function::Run).count);
  TEST_ASSERT_EQUAL_UINT8(0, mapFor(c, Function::DayNight).count);
}

void setUp(void) {}
void tearDown(void) {}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_default_timing_and_colors);
  RUN_TEST(test_experia_indicator_mapping);
  RUN_TEST(test_experia_highbeam_is_and_of_two_bits);
  RUN_TEST(test_run_and_daynight_unassigned);
  return UNITY_END();
}
