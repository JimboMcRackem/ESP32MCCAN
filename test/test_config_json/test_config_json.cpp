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
  in.flashSource = FlashSource::Auto;
  out = configFromJson(configToJson(in), ok);
  TEST_ASSERT_EQUAL_INT((int)FlashSource::Auto, (int)out.flashSource);
}

void test_unknown_flash_source_resolves_to_generate() {
  bool ok = false;
  Config a = configFromJson("{\"flashSource\":\"follow-ish\"}", ok);
  TEST_ASSERT_EQUAL_INT((int)FlashSource::Generate, (int)a.flashSource);
  Config b = configFromJson("{\"flashSource\":7}", ok);
  TEST_ASSERT_EQUAL_INT((int)FlashSource::Generate, (int)b.flashSource);
  Config c = configFromJson("{}", ok);
  TEST_ASSERT_EQUAL_INT((int)FlashSource::Generate, (int)c.flashSource);
}

void test_old_spot_hold_key_is_honoured() {
  bool ok = false;
  Config c = configFromJson("{\"spotHoldMs\":1234}", ok);
  TEST_ASSERT_EQUAL_UINT32(1234, c.nightHoldMs);
}

void test_new_hold_key_wins() {
  bool ok = false;
  Config c = configFromJson("{\"spotHoldMs\":1234,\"nightHoldMs\":900}", ok);
  TEST_ASSERT_EQUAL_UINT32(900, c.nightHoldMs);
}

void test_aux_off_on_indicate_high_beam_round_trips() {
  Config in = defaultConfig();
  TEST_ASSERT_FALSE(in.auxOffOnIndicateHighBeam);
  in.auxOffOnIndicateHighBeam = true;
  bool ok = false;
  Config out = configFromJson(configToJson(in), ok);
  TEST_ASSERT_TRUE(out.auxOffOnIndicateHighBeam);
}

void test_aux_duties_round_trip() {
  Config in = defaultConfig(); in.auxLowDuty = 22; in.auxFullDuty = 80;
  bool ok = false;
  Config out = configFromJson(configToJson(in), ok);
  TEST_ASSERT_TRUE(ok);
  TEST_ASSERT_EQUAL_UINT8(22, out.auxLowDuty);
  TEST_ASSERT_EQUAL_UINT8(80, out.auxFullDuty);
}

// 250 must not wrap a uint8_t to 250, nor -5 to 251.
void test_aux_duties_clamp_out_of_range() {
  bool ok = false;
  Config c = configFromJson("{\"auxLowDuty\":250,\"auxFullDuty\":-5}", ok);
  TEST_ASSERT_EQUAL_UINT8(100, c.auxLowDuty);
  TEST_ASSERT_EQUAL_UINT8(0, c.auxFullDuty);
}

void test_aux_duties_missing_keys_use_defaults() {
  bool ok = false;
  Config c = configFromJson("{\"blinkPeriodMs\":340}", ok);
  TEST_ASSERT_EQUAL_UINT8(15, c.auxLowDuty);
  TEST_ASSERT_EQUAL_UINT8(100, c.auxFullDuty);
}

// --- Speed / lean signals and settings (protocol 8) -----------------------

void test_round_trip_new_fields() {
  Config in = defaultConfig();
  in.speedScaleEnable = true; in.hbSlowKmh = 25; in.hbFullKmh = 90; in.hbSlowDuty = 40;
  in.leanEnable = true; in.leanStartDeg = 12; in.leanFullDeg = 35;
  in.leanBoostDuty = 70; in.leanDimDuty = 8; in.leanMinKmh = 32;
  in.speedSignal.id = 0x123; in.speedSignal.startBit = 15; in.speedSignal.length = 16;
  in.speedSignal.bigEndian = true; in.speedSignal.scale = 0.01f;
  in.leanSignal.id = 0x456; in.leanSignal.startBit = 8; in.leanSignal.length = 12;
  in.leanSignal.isSigned = true; in.leanSignal.scale = 0.1f; in.leanSignal.offset = -40.0f;
  bool ok = false;
  Config out = configFromJson(configToJson(in), ok);
  TEST_ASSERT_TRUE(ok);
  TEST_ASSERT_TRUE(out.speedScaleEnable);
  TEST_ASSERT_EQUAL_UINT16(25, out.hbSlowKmh);
  TEST_ASSERT_EQUAL_UINT16(90, out.hbFullKmh);
  TEST_ASSERT_EQUAL_UINT8(40, out.hbSlowDuty);
  TEST_ASSERT_TRUE(out.leanEnable);
  TEST_ASSERT_EQUAL_UINT8(12, out.leanStartDeg);
  TEST_ASSERT_EQUAL_UINT8(35, out.leanFullDeg);
  TEST_ASSERT_EQUAL_UINT8(70, out.leanBoostDuty);
  TEST_ASSERT_EQUAL_UINT8(8, out.leanDimDuty);
  TEST_ASSERT_EQUAL_UINT16(32, out.leanMinKmh);
  TEST_ASSERT_EQUAL_HEX32(0x123, out.speedSignal.id);
  TEST_ASSERT_EQUAL_UINT8(15, out.speedSignal.startBit);
  TEST_ASSERT_EQUAL_UINT8(16, out.speedSignal.length);
  TEST_ASSERT_TRUE(out.speedSignal.bigEndian);
  TEST_ASSERT_FALSE(out.speedSignal.isSigned);
  TEST_ASSERT_FLOAT_WITHIN(1e-6f, 0.01f, out.speedSignal.scale);
  TEST_ASSERT_EQUAL_HEX32(0x456, out.leanSignal.id);
  TEST_ASSERT_EQUAL_UINT8(8, out.leanSignal.startBit);
  TEST_ASSERT_EQUAL_UINT8(12, out.leanSignal.length);
  TEST_ASSERT_FALSE(out.leanSignal.bigEndian);
  TEST_ASSERT_TRUE(out.leanSignal.isSigned);
  TEST_ASSERT_FLOAT_WITHIN(1e-6f, 0.1f, out.leanSignal.scale);
  TEST_ASSERT_FLOAT_WITHIN(1e-6f, -40.0f, out.leanSignal.offset);
}

// Review focus 3: a config saved by protocol-7 firmware.
void test_protocol7_config_loads() {
  bool ok = false;
  Config out = configFromJson(
      "{\"blinkPeriodMs\":340,\"nightHoldMs\":800,\"auxLowDuty\":15,"
      "\"auxFullDuty\":100,\"auxOffOnIndicateHighBeam\":false,"
      "\"flashSource\":\"generate\",\"testMaxMs\":600000,"
      "\"maps\":{\"leftInd\":{\"combine\":0,\"bits\":[{\"id\":258,\"bit\":18}]}}}", ok);
  TEST_ASSERT_TRUE(ok);
  TEST_ASSERT_FALSE(out.speedScaleEnable);
  TEST_ASSERT_FALSE(out.leanEnable);
  TEST_ASSERT_FALSE(out.speedSignal.mapped());
  TEST_ASSERT_FALSE(out.leanSignal.mapped());
  TEST_ASSERT_EQUAL_UINT8(60, out.leanBoostDuty);
  TEST_ASSERT_EQUAL_UINT16(40, out.leanMinKmh);
  TEST_ASSERT_EQUAL_UINT8(1, mapFor(out, Function::LeftInd).count);
}

void test_new_field_clamps() {
  bool ok = false;
  Config out = configFromJson(
      "{\"hbSlowKmh\":999,\"hbFullKmh\":-3,\"hbSlowDuty\":300,\"leanStartDeg\":99,"
      "\"leanFullDeg\":0,\"leanBoostDuty\":250,\"leanDimDuty\":-5,\"leanMinKmh\":999,"
      "\"maps\":{\"speed\":{\"id\":1,\"start\":99,\"len\":40},"
      "\"lean\":{\"id\":2,\"start\":3,\"len\":8}}}", ok);
  TEST_ASSERT_TRUE(ok);
  TEST_ASSERT_EQUAL_UINT16(300, out.hbSlowKmh);
  TEST_ASSERT_EQUAL_UINT16(0, out.hbFullKmh);
  TEST_ASSERT_EQUAL_UINT8(100, out.hbSlowDuty);
  TEST_ASSERT_EQUAL_UINT8(60, out.leanStartDeg);
  TEST_ASSERT_EQUAL_UINT8(1, out.leanFullDeg);
  TEST_ASSERT_EQUAL_UINT8(100, out.leanBoostDuty);
  TEST_ASSERT_EQUAL_UINT8(0, out.leanDimDuty);
  TEST_ASSERT_EQUAL_UINT16(300, out.leanMinKmh);
  TEST_ASSERT_EQUAL_UINT8(0, out.speedSignal.length);     // 40 -> unmapped
  TEST_ASSERT_EQUAL_UINT8(63, out.speedSignal.startBit);
  TEST_ASSERT_EQUAL_UINT8(8, out.leanSignal.length);
  TEST_ASSERT_FLOAT_WITHIN(1e-6f, 1.0f, out.leanSignal.scale);   // absent -> 1
}

void test_signal_not_in_bit_maps() {
  bool ok = false;
  Config out = configFromJson(
      "{\"maps\":{\"speed\":{\"id\":512,\"start\":0,\"len\":16}}}", ok);
  TEST_ASSERT_TRUE(ok);
  Config def = defaultConfig();
  for (size_t i = 0; i < (size_t)Function::COUNT; ++i)
    TEST_ASSERT_EQUAL_UINT8(def.map[i].count, out.map[i].count);
  TEST_ASSERT_EQUAL_HEX32(512, out.speedSignal.id);
}

void test_unmapped_signal_not_written() {
  const std::string j = configToJson(defaultConfig());
  TEST_ASSERT_TRUE(j.find("\"speed\"") == std::string::npos);
  TEST_ASSERT_TRUE(j.find("\"lean\"") == std::string::npos);
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
  RUN_TEST(test_unknown_flash_source_resolves_to_generate);
  RUN_TEST(test_old_spot_hold_key_is_honoured);
  RUN_TEST(test_new_hold_key_wins);
  RUN_TEST(test_aux_off_on_indicate_high_beam_round_trips);
  RUN_TEST(test_aux_duties_round_trip);
  RUN_TEST(test_aux_duties_clamp_out_of_range);
  RUN_TEST(test_aux_duties_missing_keys_use_defaults);
  RUN_TEST(test_round_trip_new_fields);
  RUN_TEST(test_protocol7_config_loads);
  RUN_TEST(test_new_field_clamps);
  RUN_TEST(test_signal_not_in_bit_maps);
  RUN_TEST(test_unmapped_signal_not_written);
  return UNITY_END();
}
