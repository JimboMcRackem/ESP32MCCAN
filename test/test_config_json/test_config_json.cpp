#include <unity.h>
#include "domain/config_json.h"
#include "domain/config.h"
#include "domain/color.h"

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
  in.indicatorOrange = ColorLevel{ Rgb{255, 90, 5}, 200 };
  bool ok = false;
  Config out = configFromJson(configToJson(in), ok);
  TEST_ASSERT_TRUE(ok);
  TEST_ASSERT_TRUE((out.indicatorOrange == ColorLevel{Rgb{255, 90, 5}, 200}));
}

void test_roundtrip_preserves_test_cap() {
  Config in = defaultConfig();
  in.testMaxMs = 120000;
  bool ok = false;
  Config out = configFromJson(configToJson(in), ok);
  TEST_ASSERT_TRUE(ok);
  TEST_ASSERT_EQUAL_UINT32(120000, out.testMaxMs);
}

void test_old_rgb_triples_migrate_duty_preserving() {
  // A config written by the shipped firmware: colours are bare [r,g,b].
  const char* legacy =
    "{\"colors\":{\"drlWhiteDay\":[255,255,255],"
    "\"drlWhiteNight\":[120,120,120],"
    "\"drlDimRedDay\":[120,0,0],"
    "\"drlDimRedNight\":[60,0,0],"
    "\"indicatorOrange\":[255,80,0],"
    "\"brakeRed\":[255,0,0]}}";
  bool ok = false;
  Config c = configFromJson(legacy, ok);
  TEST_ASSERT_TRUE(ok);
  TEST_ASSERT_TRUE((resolveColor(c.drlWhiteDay)     == Rgb{255, 255, 255}));
  TEST_ASSERT_TRUE((resolveColor(c.drlWhiteNight)   == Rgb{120, 120, 120}));
  TEST_ASSERT_TRUE((resolveColor(c.drlDimRedDay)    == Rgb{120, 0, 0}));
  TEST_ASSERT_TRUE((resolveColor(c.drlDimRedNight)  == Rgb{60, 0, 0}));
  TEST_ASSERT_TRUE((resolveColor(c.indicatorOrange) == Rgb{255, 80, 0}));
  TEST_ASSERT_TRUE((resolveColor(c.brakeRed)        == Rgb{255, 0, 0}));
  // ...and the hue really was normalized, not left as the raw triple.
  TEST_ASSERT_TRUE((c.drlDimRedNight.hue == Rgb{255, 0, 0}));
}

void test_unknown_color_shape_falls_back_to_default() {
  bool ok = false;
  Config c = configFromJson("{\"colors\":{\"brakeRed\":\"scarlet\"}}", ok);
  TEST_ASSERT_TRUE(ok);
  TEST_ASSERT_TRUE((c.brakeRed == defaultConfig().brakeRed));
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
  RUN_TEST(test_roundtrip_preserves_test_cap);
  RUN_TEST(test_old_rgb_triples_migrate_duty_preserving);
  RUN_TEST(test_unknown_color_shape_falls_back_to_default);
  RUN_TEST(test_corrupt_json_falls_back_to_default);
  RUN_TEST(test_empty_string_falls_back_to_default);
  return UNITY_END();
}
