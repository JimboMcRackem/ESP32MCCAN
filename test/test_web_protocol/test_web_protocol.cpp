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
  return UNITY_END();
}
