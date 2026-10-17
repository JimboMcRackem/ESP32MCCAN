#include "domain/config_json.h"
#include <ArduinoJson.h>
#include <cstring>

static const char* kFuncNames[(size_t)Function::COUNT] = {
  "run", "leftInd", "rightInd", "frontBrake", "rearBrake",
  "lowBeam", "highBeam", "highBeamFlash", "dayNight", "kickStand"
};

std::string configToJson(const Config& c) {
  JsonDocument doc;

  JsonObject maps = doc["maps"].to<JsonObject>();
  for (size_t i = 0; i < (size_t)Function::COUNT; ++i) {
    const FunctionMap& fm = c.map[i];
    JsonObject m = maps[kFuncNames[i]].to<JsonObject>();
    m["combine"] = (int)fm.combine;
    JsonArray bits = m["bits"].to<JsonArray>();
    for (uint8_t b = 0; b < fm.count; ++b) {
      JsonObject br = bits.add<JsonObject>();
      br["id"] = fm.bits[b].id;
      br["bit"] = fm.bits[b].bit;
    }
  }

  doc["blinkPeriodMs"] = c.blinkPeriodMs;
  doc["spotHoldMs"] = c.spotHoldMs;
  static const char* kFlashSourceNames[] = { "auto", "follow", "generate" };
  doc["flashSource"] = kFlashSourceNames[(uint8_t)c.flashSource];
  doc["testMaxMs"] = c.testMaxMs;

  std::string out;
  serializeJson(doc, out);
  return out;
}

Config configFromJson(const std::string& json, bool& ok) {
  JsonDocument doc;
  if (deserializeJson(doc, json) != DeserializationError::Ok) {
    ok = false;
    return defaultConfig();
  }
  ok = true;
  Config c = defaultConfig();   // start from defaults, override present fields

  JsonObjectConst maps = doc["maps"];
  if (!maps.isNull()) {
    for (size_t i = 0; i < (size_t)Function::COUNT; ++i) {
      JsonObjectConst m = maps[kFuncNames[i]];
      if (m.isNull()) continue;
      FunctionMap fm;
      fm.combine = (Combine)(m["combine"] | 0);
      JsonArrayConst bits = m["bits"];
      uint8_t n = 0;
      for (JsonObjectConst br : bits) {
        if (n >= FunctionMap::MAX_BITS) break;
        fm.bits[n].id = br["id"] | 0u;
        fm.bits[n].bit = (uint8_t)(br["bit"] | 0);
        ++n;
      }
      fm.count = n;
      c.map[i] = fm;
    }
  }

  c.blinkPeriodMs = doc["blinkPeriodMs"] | c.blinkPeriodMs;
  c.spotHoldMs = doc["spotHoldMs"] | c.spotHoldMs;
  // Unknown or non-string values resolve to Auto rather than to an undefined
  // enum value: an unreadable setting must not change how the bike signals.
  const char* fs = doc["flashSource"].as<const char*>();
  c.flashSource = FlashSource::Auto;
  if (fs) {
    if (!strcmp(fs, "follow"))        c.flashSource = FlashSource::Follow;
    else if (!strcmp(fs, "generate")) c.flashSource = FlashSource::Generate;
  }
  c.testMaxMs = doc["testMaxMs"] | c.testMaxMs;

  return c;
}
