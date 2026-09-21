#include <unity.h>
#include "domain/web_protocol.h"
#include "domain/config_json.h"
#include "domain/config.h"
#include "domain/can_state.h"
#include <ArduinoJson.h>

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

void test_test_zones_parse_in_corner_order(void) {
  ProtocolAction a = handleRequest(
      "{\"type\":\"test\",\"mode\":\"zones\",\"zones\":"
      "[[255,80,0],[0,0,0],[255,0,0],[1,2,3]],\"denali\":128}");
  TEST_ASSERT_TRUE(a.setTest);
  TEST_ASSERT_TRUE(a.error.empty());
  TEST_ASSERT_TRUE(a.testOut.kind == TestKind::Zones);
  TEST_ASSERT_TRUE((a.testOut.zones.frontL == Rgb{255, 80, 0}));
  TEST_ASSERT_TRUE((a.testOut.zones.frontR == Rgb{0, 0, 0}));
  TEST_ASSERT_TRUE((a.testOut.zones.rearL == Rgb{255, 0, 0}));
  TEST_ASSERT_TRUE((a.testOut.zones.rearR == Rgb{1, 2, 3}));
  TEST_ASSERT_EQUAL_UINT8(128, a.testOut.zones.denali);
}

void test_test_zones_denali_defaults_to_zero(void) {
  ProtocolAction a = handleRequest(
      "{\"type\":\"test\",\"mode\":\"zones\",\"zones\":"
      "[[1,1,1],[1,1,1],[1,1,1],[1,1,1]]}");
  TEST_ASSERT_TRUE(a.setTest);
  TEST_ASSERT_EQUAL_UINT8(0, a.testOut.zones.denali);
}

void test_test_zones_reject_wrong_length(void) {
  ProtocolAction a = handleRequest(
      "{\"type\":\"test\",\"mode\":\"zones\",\"zones\":[[1,1,1],[2,2,2]]}");
  TEST_ASSERT_FALSE(a.setTest);
  TEST_ASSERT_FALSE(a.error.empty());
}

void test_test_zones_reject_out_of_range_values(void) {
  ProtocolAction hi = handleRequest(
      "{\"type\":\"test\",\"mode\":\"zones\",\"zones\":"
      "[[256,0,0],[0,0,0],[0,0,0],[0,0,0]]}");
  TEST_ASSERT_FALSE(hi.setTest);
  TEST_ASSERT_FALSE(hi.error.empty());

  ProtocolAction lo = handleRequest(
      "{\"type\":\"test\",\"mode\":\"zones\",\"zones\":"
      "[[0,-1,0],[0,0,0],[0,0,0],[0,0,0]]}");
  TEST_ASSERT_FALSE(lo.setTest);
  TEST_ASSERT_FALSE(lo.error.empty());
}

void test_test_zones_reject_a_short_triple(void) {
  ProtocolAction a = handleRequest(
      "{\"type\":\"test\",\"mode\":\"zones\",\"zones\":"
      "[[1,1],[0,0,0],[0,0,0],[0,0,0]]}");
  TEST_ASSERT_FALSE(a.setTest);
  TEST_ASSERT_FALSE(a.error.empty());
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
  TEST_ASSERT_EQUAL_INT(2, kProtocolVersion);
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
  RUN_TEST(test_test_zones_parse_in_corner_order);
  RUN_TEST(test_test_zones_denali_defaults_to_zero);
  RUN_TEST(test_test_zones_reject_wrong_length);
  RUN_TEST(test_test_zones_reject_out_of_range_values);
  RUN_TEST(test_test_zones_reject_a_short_triple);
  RUN_TEST(test_test_rejects_an_unknown_mode);
  RUN_TEST(test_config_message_carries_the_protocol_version);
  RUN_TEST(test_test_state_message_shape);
  RUN_TEST(test_test_state_message_when_off);
  RUN_TEST(test_test_state_remaining_clamps_at_zero);
  return UNITY_END();
}
