#include <unity.h>
#include <string>
#include "domain/wifi_settings.h"
#include "domain/reset_hold.h"

void setUp(void) {}
void tearDown(void) {}

void test_password_boundaries(void) {
  TEST_ASSERT_EQUAL(PasswordCheck::TooShort, checkWifiPassword("1234567"));
  TEST_ASSERT_EQUAL(PasswordCheck::Ok, checkWifiPassword("12345678"));
  TEST_ASSERT_EQUAL(PasswordCheck::Ok, checkWifiPassword(std::string(63, 'a')));
  TEST_ASSERT_EQUAL(PasswordCheck::TooLong, checkWifiPassword(std::string(64, 'a')));
  TEST_ASSERT_EQUAL(PasswordCheck::Ok, checkWifiPassword("password "));
  TEST_ASSERT_EQUAL(PasswordCheck::BadChar, checkWifiPassword("p\xC3\xA4ssword1"));
  TEST_ASSERT_EQUAL(PasswordCheck::TooShort, checkWifiPassword(""));
}

void test_password_texts(void) {
  TEST_ASSERT_EQUAL_STRING("Wi-Fi password must be at least 8 characters.", passwordCheckText(PasswordCheck::TooShort));
  TEST_ASSERT_EQUAL_STRING("Wi-Fi password must be at most 63 characters.", passwordCheckText(PasswordCheck::TooLong));
  TEST_ASSERT_EQUAL_STRING("Wi-Fi password may only use plain letters, digits, spaces and symbols.", passwordCheckText(PasswordCheck::BadChar));
}

void test_default_password_is_valid(void) {
  TEST_ASSERT_EQUAL(PasswordCheck::Ok, checkWifiPassword(kDefaultWifiPassword));
}

void test_ssid_from_mac(void) {
  const uint8_t a[6] = {0x24, 0x6F, 0x28, 0xAB, 0x3F, 0x2A};
  const uint8_t b[6] = {0x24, 0x6F, 0x28, 0xAB, 0x00, 0x0A};
  TEST_ASSERT_EQUAL_STRING("MCCAN-3F2A", apSsid(a).c_str());
  TEST_ASSERT_EQUAL_STRING("MCCAN-000A", apSsid(b).c_str());
}

void test_config_source(void) {
  TEST_ASSERT_EQUAL(ConfigSource::Nvs, pickConfigSource(true, true));
  TEST_ASSERT_EQUAL(ConfigSource::Nvs, pickConfigSource(true, false));
  TEST_ASSERT_EQUAL(ConfigSource::Legacy, pickConfigSource(false, true));
  TEST_ASSERT_EQUAL(ConfigSource::Defaults, pickConfigSource(false, false));
}

void test_short_press_does_nothing(void) {
  ResetHold h;
  for (uint32_t t = 0; t <= 3000; t += 10) TEST_ASSERT_FALSE(h.update(true, t));
  for (uint32_t t = 3010; t <= 20000; t += 10) TEST_ASSERT_FALSE(h.update(false, t));
}

void test_fires_at_ten_seconds(void) {
  ResetHold h;
  for (uint32_t t = 1000; t < 11000; t += 10) TEST_ASSERT_FALSE(h.update(true, t));
  TEST_ASSERT_FALSE(h.update(true, 10999));
  TEST_ASSERT_TRUE(h.update(true, 11000));
}

void test_bounce_ignored(void) {
  ResetHold h;
  uint32_t t = 0;
  for (; t < 4000; t += 10) TEST_ASSERT_FALSE(h.update(true, t));
  for (; t < 4020; t += 10) TEST_ASSERT_FALSE(h.update(false, t));
  bool fired = false;
  for (t = 4020; t < 10000; t += 10) fired |= h.update(true, t);
  TEST_ASSERT_FALSE(fired);
  TEST_ASSERT_TRUE(h.update(true, 10000));
}

void test_release_restarts_count(void) {
  ResetHold h;
  uint32_t t = 0;
  for (; t < 4000; t += 10) TEST_ASSERT_FALSE(h.update(true, t));
  for (; t < 4060; t += 10) TEST_ASSERT_FALSE(h.update(false, t));
  bool fired = false;
  for (t = 4060; t < 14060; t += 10) fired |= h.update(true, t);
  TEST_ASSERT_FALSE(fired);
  TEST_ASSERT_TRUE(h.update(true, 14060));
}

void test_fires_once_per_hold(void) {
  ResetHold h;
  int fires = 0;
  uint32_t t = 0;
  for (; t <= 20000; t += 10) fires += h.update(true, t) ? 1 : 0;
  TEST_ASSERT_EQUAL(1, fires);
  for (uint32_t e = t + 100; t < e; t += 10) h.update(false, t);
  for (uint32_t e = t + 10000; t <= e; t += 10) fires += h.update(true, t) ? 1 : 0;
  TEST_ASSERT_EQUAL(2, fires);
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_password_boundaries);
  RUN_TEST(test_password_texts);
  RUN_TEST(test_default_password_is_valid);
  RUN_TEST(test_ssid_from_mac);
  RUN_TEST(test_config_source);
  RUN_TEST(test_short_press_does_nothing);
  RUN_TEST(test_fires_at_ten_seconds);
  RUN_TEST(test_bounce_ignored);
  RUN_TEST(test_release_restarts_count);
  RUN_TEST(test_fires_once_per_hold);
  return UNITY_END();
}
