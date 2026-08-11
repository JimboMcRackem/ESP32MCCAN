#include <unity.h>
#include "domain/config_json.h"
#include "domain/config.h"

void test_roundtrip_preserves_mapping_and_tunables() {
  Config in = defaultConfig();
  in.blinkPeriodMs = 500;
  in.denaliSpot = 200;
  bool ok = false;
  Config out = configFromJson(configToJson(in), ok);
  TEST_ASSERT_TRUE(ok);
  TEST_ASSERT_EQUAL_UINT32(500, out.blinkPeriodMs);
  TEST_ASSERT_EQUAL_UINT8(200, out.denaliSpot);
  const FunctionMap& hb = mapFor(out, Function::HighBeam);
  TEST_ASSERT_EQUAL(Combine::And, hb.combine);
  TEST_ASSERT_EQUAL_UINT8(2, hb.count);
  TEST_ASSERT_EQUAL_UINT8(16, hb.bits[1].bit);
  const FunctionMap& left = mapFor(out, Function::LeftInd);
  TEST_ASSERT_EQUAL_HEX32(0x102, left.bits[0].id);
  TEST_ASSERT_EQUAL_UINT8(18, left.bits[0].bit);
}

void test_roundtrip_preserves_colors() {
  Config in = defaultConfig();
  in.indicatorOrange = {250, 90, 5};
  bool ok = false;
  Config out = configFromJson(configToJson(in), ok);
  TEST_ASSERT_TRUE((out.indicatorOrange == Rgb{250, 90, 5}));
}

void test_corrupt_json_falls_back_to_default() {
  bool ok = true;
  Config out = configFromJson("{not valid json", ok);
  TEST_ASSERT_FALSE(ok);
  TEST_ASSERT_EQUAL_UINT32(340, out.blinkPeriodMs);       // default
  TEST_ASSERT_EQUAL_UINT8(1, mapFor(out, Function::LeftInd).count);
}

void test_empty_string_falls_back_to_default() {
  bool ok = true;
  Config out = configFromJson("", ok);
  TEST_ASSERT_FALSE(ok);
  TEST_ASSERT_EQUAL_UINT32(340, out.blinkPeriodMs);
}

void setUp(void) {}
void tearDown(void) {}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_roundtrip_preserves_mapping_and_tunables);
  RUN_TEST(test_roundtrip_preserves_colors);
  RUN_TEST(test_corrupt_json_falls_back_to_default);
  RUN_TEST(test_empty_string_falls_back_to_default);
  return UNITY_END();
}
