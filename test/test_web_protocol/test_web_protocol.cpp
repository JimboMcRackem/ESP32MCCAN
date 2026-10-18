#include <unity.h>
#include "domain/web_protocol.h"
#include "domain/config_json.h"
#include "domain/config.h"
#include "domain/can_state.h"
#include <ArduinoJson.h>
#include <cstring>
#include <cstdio>

void setUp(void) {}
void tearDown(void) {}

void test_get_config_requests_send(void) {
  ProtocolAction a = handleRequest("{\"type\":\"get_config\"}");
  TEST_ASSERT_TRUE(a.sendConfig);
  TEST_ASSERT_FALSE(a.applyConfig);
  TEST_ASSERT_TRUE(a.error.empty());
}

void test_set_config_applies_and_parses(void) {
  // Build a valid config doc and wrap it in a set_config envelope.
  Config c = defaultConfig();
  c.blinkPeriodMs = 500;
  std::string body = configToJson(c);
  std::string req = std::string("{\"type\":\"set_config\",\"config\":") + body + "}";

  ProtocolAction a = handleRequest(req);
  TEST_ASSERT_TRUE(a.applyConfig);
  TEST_ASSERT_TRUE(a.error.empty());
  TEST_ASSERT_EQUAL_UINT32(500, a.cfgOut.blinkPeriodMs);
}

void test_set_config_missing_body_is_error(void) {
  ProtocolAction a = handleRequest("{\"type\":\"set_config\"}");
  TEST_ASSERT_FALSE(a.applyConfig);
  TEST_ASSERT_FALSE(a.error.empty());
}

void test_malformed_json_is_error(void) {
  ProtocolAction a = handleRequest("not json");
  TEST_ASSERT_FALSE(a.error.empty());
}

void test_unknown_type_is_error(void) {
  ProtocolAction a = handleRequest("{\"type\":\"bogus\"}");
  TEST_ASSERT_FALSE(a.error.empty());
}

void test_discovery_enable_and_disable(void) {
  ProtocolAction on = handleRequest("{\"type\":\"discovery\",\"enable\":true}");
  TEST_ASSERT_TRUE(on.setDiscovery);
  TEST_ASSERT_TRUE(on.discoveryOut);

  ProtocolAction off = handleRequest("{\"type\":\"discovery\",\"enable\":false}");
  TEST_ASSERT_TRUE(off.setDiscovery);
  TEST_ASSERT_FALSE(off.discoveryOut);
}

void test_config_message_round_trips(void) {
  Config c = defaultConfig();
  c.spotHoldMs = 1234;
  std::string msg = configMessage(c);

  // Envelope has type=config; nested config re-parses to the same value.
  JsonDocument doc;
  TEST_ASSERT_TRUE(deserializeJson(doc, msg) == DeserializationError::Ok);
  TEST_ASSERT_EQUAL_STRING("config", doc["type"].as<const char*>());

  std::string inner;
  serializeJson(doc["config"], inner);
  bool ok = false;
  Config back = configFromJson(inner, ok);
  TEST_ASSERT_TRUE(ok);
  TEST_ASSERT_EQUAL_UINT32(1234, back.spotHoldMs);
}

void test_frames_message_serializes_ids_and_bytes(void) {
  CanFrameSnapshot fr[2];
  fr[0].id = 0x102; for (int i = 0; i < 8; ++i) fr[0].data[i] = 0; fr[0].data[0] = 0xAB;
  fr[1].id = 0x400; for (int i = 0; i < 8; ++i) fr[1].data[i] = 0; fr[1].data[7] = 0x0F;

  std::string msg = framesMessage(fr, 2);
  JsonDocument doc;
  TEST_ASSERT_TRUE(deserializeJson(doc, msg) == DeserializationError::Ok);
  TEST_ASSERT_EQUAL_STRING("frames", doc["type"].as<const char*>());
  JsonArray arr = doc["frames"].as<JsonArray>();
  TEST_ASSERT_EQUAL_INT(2, arr.size());
  TEST_ASSERT_EQUAL_UINT32(0x102, arr[0]["id"].as<uint32_t>());
  TEST_ASSERT_EQUAL_UINT8(0xAB, arr[0]["data"][0].as<uint8_t>());
  TEST_ASSERT_EQUAL_UINT8(0x0F, arr[1]["data"][7].as<uint8_t>());
}

void test_error_message_shape(void) {
  std::string msg = errorMessage("boom");
  JsonDocument doc;
  TEST_ASSERT_TRUE(deserializeJson(doc, msg) == DeserializationError::Ok);
  TEST_ASSERT_EQUAL_STRING("error", doc["type"].as<const char*>());
  TEST_ASSERT_EQUAL_STRING("boom", doc["message"].as<const char*>());
}

void test_test_off_is_accepted(void) {
  ProtocolAction a = handleRequest("{\"type\":\"test\",\"mode\":\"off\"}");
  TEST_ASSERT_TRUE(a.setTest);
  TEST_ASSERT_TRUE(a.error.empty());
  TEST_ASSERT_TRUE(a.testOut.kind == TestKind::Off);
}

void test_test_scenario_resolves_the_preset(void) {
  ProtocolAction a = handleRequest(
      "{\"type\":\"test\",\"mode\":\"scenario\",\"scenario\":\"hazards\"}");
  TEST_ASSERT_TRUE(a.setTest);
  TEST_ASSERT_TRUE(a.error.empty());
  TEST_ASSERT_TRUE(a.testOut.kind == TestKind::Scenario);
  TEST_ASSERT_TRUE(a.testOut.scenario.leftInd);
  TEST_ASSERT_TRUE(a.testOut.scenario.rightInd);
}

void test_unknown_scenario_is_an_error(void) {
  ProtocolAction a = handleRequest(
      "{\"type\":\"test\",\"mode\":\"scenario\",\"scenario\":\"disco\"}");
  TEST_ASSERT_FALSE(a.setTest);
  TEST_ASSERT_FALSE(a.error.empty());
}

// NOTE: the zones wire format moved from 4 rgb corner triples to a 12-bit
// output mask when OutputIntent's shape changed underneath TestMode::zones.
// The old corner-triple tests that lived here are gone because that shape no
// longer exists; full mask-format coverage (and the protocol version bump)
// belongs to the task that finishes the wire protocol rework.

void test_zones_request_parses_a_twelve_bit_mask() {
  const unsigned want = (unsigned)outMask(OUT_RL_BRK, OUT_AUX_L);
  char buf[128];
  snprintf(buf, sizeof buf,
           "{\"type\":\"test\",\"mode\":\"zones\",\"zones\":%u}", want);
  ProtocolAction a = handleRequest(buf);
  TEST_ASSERT_TRUE(a.setTest);
  TEST_ASSERT_TRUE(a.error.empty());
  TEST_ASSERT_EQUAL_INT((int)TestKind::Zones, (int)a.testOut.kind);
  TEST_ASSERT_EQUAL_UINT16((uint16_t)want, a.testOut.zones.on);
}

void test_zones_request_rejects_bits_above_the_output_count() {
  ProtocolAction a = handleRequest(
    "{\"type\":\"test\",\"mode\":\"zones\",\"zones\":65535}");
  TEST_ASSERT_FALSE(a.error.empty());   // must not silently truncate
}

void test_test_state_message_reports_the_zone_mask() {
  TestMode t;
  t.kind = TestKind::Zones;
  t.zones.on = outMask(OUT_FR_IND);
  char want[64];
  snprintf(want, sizeof want, "\"zones\":%u", (unsigned)outMask(OUT_FR_IND));
  const std::string m = testStateMessage(t, defaultConfig(), 0);
  TEST_ASSERT_NOT_NULL(strstr(m.c_str(), want));
}

void test_zones_request_rejects_a_missing_zones_field() {
  // No "zones" key at all: must error, not default to mask 0 and report
  // success for a request that never said what to energise.
  ProtocolAction a = handleRequest("{\"type\":\"test\",\"mode\":\"zones\"}");
  TEST_ASSERT_FALSE(a.setTest);
  TEST_ASSERT_FALSE(a.error.empty());
}

void test_protocol_version_is_three() {
  TEST_ASSERT_EQUAL_INT(3, kProtocolVersion);
}

void test_config_message_carries_flash_source_and_no_colours() {
  Config c = defaultConfig();
  c.flashSource = FlashSource::Follow;
  const std::string m = configMessage(c);
  TEST_ASSERT_NOT_NULL(strstr(m.c_str(), "\"flashSource\":\"follow\""));
  TEST_ASSERT_NULL(strstr(m.c_str(), "colors"));
  TEST_ASSERT_NULL(strstr(m.c_str(), "denali"));
}

void test_test_rejects_an_unknown_mode(void) {
  ProtocolAction a = handleRequest("{\"type\":\"test\",\"mode\":\"strobe\"}");
  TEST_ASSERT_FALSE(a.setTest);
  TEST_ASSERT_FALSE(a.error.empty());
}

void test_config_message_carries_the_protocol_version(void) {
  std::string msg = configMessage(defaultConfig());
  JsonDocument doc;
  TEST_ASSERT_TRUE(deserializeJson(doc, msg) == DeserializationError::Ok);
  TEST_ASSERT_EQUAL_INT(kProtocolVersion, doc["protocolVersion"].as<int>());
  TEST_ASSERT_EQUAL_INT(3, kProtocolVersion);
}

void test_test_state_message_shape(void) {
  Config cfg = defaultConfig();
  TestMode t;
  t.kind = TestKind::Zones;
  t.startedMs = 1000;

  JsonDocument doc;
  std::string msg = testStateMessage(t, cfg, 1000 + 11000);
  TEST_ASSERT_TRUE(deserializeJson(doc, msg) == DeserializationError::Ok);
  TEST_ASSERT_EQUAL_STRING("test_state", doc["type"].as<const char*>());
  TEST_ASSERT_TRUE(doc["active"].as<bool>());
  TEST_ASSERT_EQUAL_STRING("zones", doc["kind"].as<const char*>());
  TEST_ASSERT_EQUAL_UINT32(cfg.testMaxMs - 11000, doc["remainingMs"].as<uint32_t>());
}

void test_test_state_message_when_off(void) {
  Config cfg = defaultConfig();
  TestMode t;                                   // Off
  JsonDocument doc;
  std::string msg = testStateMessage(t, cfg, 500000);
  TEST_ASSERT_TRUE(deserializeJson(doc, msg) == DeserializationError::Ok);
  TEST_ASSERT_FALSE(doc["active"].as<bool>());
  TEST_ASSERT_EQUAL_STRING("off", doc["kind"].as<const char*>());
  TEST_ASSERT_EQUAL_UINT32(0, doc["remainingMs"].as<uint32_t>());
}

void test_test_state_remaining_clamps_at_zero(void) {
  Config cfg = defaultConfig();
  TestMode t;
  t.kind = TestKind::Scenario;
  t.startedMs = 0;
  JsonDocument doc;
  std::string msg = testStateMessage(t, cfg, cfg.testMaxMs + 5000);
  TEST_ASSERT_TRUE(deserializeJson(doc, msg) == DeserializationError::Ok);
  TEST_ASSERT_EQUAL_UINT32(0, doc["remainingMs"].as<uint32_t>());
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_get_config_requests_send);
  RUN_TEST(test_set_config_applies_and_parses);
  RUN_TEST(test_set_config_missing_body_is_error);
  RUN_TEST(test_malformed_json_is_error);
  RUN_TEST(test_unknown_type_is_error);
  RUN_TEST(test_discovery_enable_and_disable);
  RUN_TEST(test_config_message_round_trips);
  RUN_TEST(test_frames_message_serializes_ids_and_bytes);
  RUN_TEST(test_error_message_shape);
  RUN_TEST(test_test_off_is_accepted);
  RUN_TEST(test_test_scenario_resolves_the_preset);
  RUN_TEST(test_unknown_scenario_is_an_error);
  RUN_TEST(test_zones_request_parses_a_twelve_bit_mask);
  RUN_TEST(test_zones_request_rejects_bits_above_the_output_count);
  RUN_TEST(test_zones_request_rejects_a_missing_zones_field);
  RUN_TEST(test_test_state_message_reports_the_zone_mask);
  RUN_TEST(test_test_rejects_an_unknown_mode);
  RUN_TEST(test_config_message_carries_the_protocol_version);
  RUN_TEST(test_protocol_version_is_three);
  RUN_TEST(test_config_message_carries_flash_source_and_no_colours);
  RUN_TEST(test_test_state_message_shape);
  RUN_TEST(test_test_state_message_when_off);
  RUN_TEST(test_test_state_remaining_clamps_at_zero);
  return UNITY_END();
}
