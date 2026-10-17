#include <unity.h>
#include "domain/config_json.h"
#include "domain/config.h"

void test_roundtrip_preserves_mapping_and_tunables() {
  Config in = defaultConfig();
  in.blinkPeriodMs = 500;
  bool ok = false;
  Config out = configFromJson(configToJson(in), ok);
  TEST_ASSERT_TRUE(ok);
  TEST_ASSERT_EQUAL_UINT32(500, out.blinkPeriodMs);
  const FunctionMap& hb = mapFor(out, Function::HighBeam);
  TEST_ASSERT_EQUAL(Combine::And, hb.combine);
  TEST_ASSERT_EQUAL_UINT8(2, hb.count);
  TEST_ASSERT_EQUAL_UINT8(16, hb.bits[1].bit);
  const FunctionMap& left = mapFor(out, Function::LeftInd);
  TEST_ASSERT_EQUAL_HEX32(0x102, left.bits[0].id);
  TEST_ASSERT_EQUAL_UINT8(18, left.bits[0].bit);
}

void test_roundtrip_preserves_test_cap() {
  Config in = defaultConfig();
  in.testMaxMs = 120000;
  bool ok = false;
  Config out = configFromJson(configToJson(in), ok);
  TEST_ASSERT_TRUE(ok);
  TEST_ASSERT_EQUAL_UINT32(120000, out.testMaxMs);
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

void test_config_written_by_the_previous_firmware_still_loads() {
  // Shape the old firmware wrote: colours and denali present, no flashSource.
  const std::string old =
    "{\"maps\":{\"leftInd\":{\"combine\":0,"
    "\"bits\":[{\"id\":258,\"bit\":18}]}},"
    "\"blinkPeriodMs\":500,"
    "\"colors\":{\"brakeRed\":{\"hue\":[255,0,0],\"level\":255}},"
    "\"denali\":{\"day\":50,\"low\":128,\"high\":255,\"spot\":255}}";
  bool ok = false;
  Config c = configFromJson(old, ok);
  TEST_ASSERT_TRUE(ok);                      // not a wholesale fallback
  TEST_ASSERT_EQUAL_UINT32(500, c.blinkPeriodMs);
  const FunctionMap& fm = mapFor(c, Function::LeftInd);
  TEST_ASSERT_EQUAL_UINT8(1, fm.count);      // mappings survived
  TEST_ASSERT_EQUAL_UINT32(258, fm.bits[0].id);
  TEST_ASSERT_EQUAL_UINT8(18, fm.bits[0].bit);
}

void test_flash_source_round_trips() {
  Config in = defaultConfig();
  in.flashSource = FlashSource::Generate;
  bool ok = false;
  Config out = configFromJson(configToJson(in), ok);
  TEST_ASSERT_TRUE(ok);
  TEST_ASSERT_EQUAL_INT((int)FlashSource::Generate, (int)out.flashSource);
}

void test_unknown_flash_source_resolves_to_auto() {
  bool ok = false;
  Config a = configFromJson("{\"flashSource\":\"follow-ish\"}", ok);
  TEST_ASSERT_EQUAL_INT((int)FlashSource::Auto, (int)a.flashSource);
  Config b = configFromJson("{\"flashSource\":7}", ok);
  TEST_ASSERT_EQUAL_INT((int)FlashSource::Auto, (int)b.flashSource);
  Config c = configFromJson("{}", ok);
  TEST_ASSERT_EQUAL_INT((int)FlashSource::Auto, (int)c.flashSource);
}

void setUp(void) {}
void tearDown(void) {}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_roundtrip_preserves_mapping_and_tunables);
  RUN_TEST(test_roundtrip_preserves_test_cap);
  RUN_TEST(test_corrupt_json_falls_back_to_default);
  RUN_TEST(test_empty_string_falls_back_to_default);
  RUN_TEST(test_config_written_by_the_previous_firmware_still_loads);
  RUN_TEST(test_flash_source_round_trips);
  RUN_TEST(test_unknown_flash_source_resolves_to_auto);
  return UNITY_END();
}
