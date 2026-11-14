#include "domain/wifi_settings.h"
#include <cstdio>

PasswordCheck checkWifiPassword(const std::string& p) {
  if (p.size() < 8) return PasswordCheck::TooShort;
  if (p.size() > 63) return PasswordCheck::TooLong;
  for (unsigned char c : p)
    if (c < 0x20 || c > 0x7E) return PasswordCheck::BadChar;
  return PasswordCheck::Ok;
}

const char* passwordCheckText(PasswordCheck c) {
  switch (c) {
    case PasswordCheck::TooShort: return "Wi-Fi password must be at least 8 characters.";
    case PasswordCheck::TooLong:  return "Wi-Fi password must be at most 63 characters.";
    case PasswordCheck::BadChar:  return "Wi-Fi password may only use plain letters, digits, spaces and symbols.";
    case PasswordCheck::Ok:       break;
  }
  return "";
}

std::string apSsid(const uint8_t mac[6]) {
  char buf[16];
  snprintf(buf, sizeof buf, "MCCAN-%02X%02X", mac[4], mac[5]);
  return buf;
}

ConfigSource pickConfigSource(bool nvsHasConfig, bool legacyHasConfig) {
  if (nvsHasConfig) return ConfigSource::Nvs;
  if (legacyHasConfig) return ConfigSource::Legacy;
  return ConfigSource::Defaults;
}
