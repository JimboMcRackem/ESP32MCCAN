#pragma once
#include <cstdint>
#include <string>

constexpr const char* kDefaultWifiPassword = "mccan1234";

enum class PasswordCheck { Ok, TooShort, TooLong, BadChar };

// 8..63 bytes, each 0x20..0x7E.
PasswordCheck checkWifiPassword(const std::string& p);
const char* passwordCheckText(PasswordCheck c);

// "MCCAN-" + last two MAC bytes as upper-case hex.
std::string apSsid(const uint8_t mac[6]);

enum class ConfigSource { Nvs, Legacy, Defaults };
// NVS wins, then the legacy file, then built-in defaults.
ConfigSource pickConfigSource(bool nvsHasConfig, bool legacyHasConfig);
