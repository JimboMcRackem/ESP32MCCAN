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

void test_experia_all_single_bit_mappings() {
  Config c = defaultConfig();

  // RightInd → bit 19
  const FunctionMap& rightInd = mapFor(c, Function::RightInd);
  TEST_ASSERT_EQUAL_UINT8(1, rightInd.count);
  TEST_ASSERT_EQUAL_HEX32(0x102, rightInd.bits[0].id);
  TEST_ASSERT_EQUAL_UINT8(19, rightInd.bits[0].bit);

  // FrontBrake → bit 21
  const FunctionMap& frontBrake = mapFor(c, Function::FrontBrake);
  TEST_ASSERT_EQUAL_UINT8(1, frontBrake.count);
  TEST_ASSERT_EQUAL_HEX32(0x102, frontBrake.bits[0].id);
  TEST_ASSERT_EQUAL_UINT8(21, frontBrake.bits[0].bit);

  // RearBrake → bit 22
  const FunctionMap& rearBrake = mapFor(c, Function::RearBrake);
  TEST_ASSERT_EQUAL_UINT8(1, rearBrake.count);
  TEST_ASSERT_EQUAL_HEX32(0x102, rearBrake.bits[0].id);
  TEST_ASSERT_EQUAL_UINT8(22, rearBrake.bits[0].bit);

  // LowBeam → bit 7
  const FunctionMap& lowBeam = mapFor(c, Function::LowBeam);
  TEST_ASSERT_EQUAL_UINT8(1, lowBeam.count);
  TEST_ASSERT_EQUAL_HEX32(0x102, lowBeam.bits[0].id);
  TEST_ASSERT_EQUAL_UINT8(7, lowBeam.bits[0].bit);

  // HighBeamFlash → bit 16
  const FunctionMap& highBeamFlash = mapFor(c, Function::HighBeamFlash);
  TEST_ASSERT_EQUAL_UINT8(1, highBeamFlash.count);
  TEST_ASSERT_EQUAL_HEX32(0x102, highBeamFlash.bits[0].id);
  TEST_ASSERT_EQUAL_UINT8(16, highBeamFlash.bits[0].bit);

  // KickStand → bit 13
  const FunctionMap& kickStand = mapFor(c, Function::KickStand);
  TEST_ASSERT_EQUAL_UINT8(1, kickStand.count);
  TEST_ASSERT_EQUAL_HEX32(0x102, kickStand.bits[0].id);
  TEST_ASSERT_EQUAL_UINT8(13, kickStand.bits[0].bit);
}

void test_default_colors_and_denali_levels() {
  Config c = defaultConfig();

  // Test all remaining color defaults
  TEST_ASSERT_TRUE((c.drlWhiteDay == Rgb{255, 255, 255}));
  TEST_ASSERT_TRUE((c.drlWhiteNight == Rgb{120, 120, 120}));
  TEST_ASSERT_TRUE((c.drlDimRedDay == Rgb{120, 0, 0}));
  TEST_ASSERT_TRUE((c.drlDimRedNight == Rgb{60, 0, 0}));
  TEST_ASSERT_TRUE((c.brakeRed == Rgb{255, 0, 0}));

  // Test all Denali levels
  TEST_ASSERT_EQUAL_UINT8(50, c.denaliDay);
  TEST_ASSERT_EQUAL_UINT8(128, c.denaliLow);
  TEST_ASSERT_EQUAL_UINT8(255, c.denaliHigh);
  TEST_ASSERT_EQUAL_UINT8(255, c.denaliSpot);
}

void setUp(void) {}
void tearDown(void) {}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_default_timing_and_colors);
  RUN_TEST(test_experia_indicator_mapping);
  RUN_TEST(test_experia_highbeam_is_and_of_two_bits);
  RUN_TEST(test_run_and_daynight_unassigned);
  RUN_TEST(test_experia_all_single_bit_mappings);
  RUN_TEST(test_default_colors_and_denali_levels);
  return UNITY_END();
}
