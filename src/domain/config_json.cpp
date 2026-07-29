#include "domain/config_json.h"
#include <ArduinoJson.h>

static const char* kFuncNames[(size_t)Function::COUNT] = {
  "run", "leftInd", "rightInd", "frontBrake", "rearBrake",
  "lowBeam", "highBeam", "highBeamFlash", "dayNight", "kickStand"
};

static void rgbTo(JsonArray a, const Rgb& c) { a.add(c.r); a.add(c.g); a.add(c.b); }
static Rgb rgbFrom(JsonArrayConst a, Rgb def) {
  if (a.size() != 3) return def;
  return Rgb{ (uint8_t)a[0].as<int>(), (uint8_t)a[1].as<int>(), (uint8_t)a[2].as<int>() };
}

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

  JsonObject col = doc["colors"].to<JsonObject>();
  rgbTo(col["drlWhiteDay"].to<JsonArray>(), c.drlWhiteDay);
  rgbTo(col["drlWhiteNight"].to<JsonArray>(), c.drlWhiteNight);
  rgbTo(col["drlDimRedDay"].to<JsonArray>(), c.drlDimRedDay);
  rgbTo(col["drlDimRedNight"].to<JsonArray>(), c.drlDimRedNight);
  rgbTo(col["indicatorOrange"].to<JsonArray>(), c.indicatorOrange);
  rgbTo(col["brakeRed"].to<JsonArray>(), c.brakeRed);

  JsonObject den = doc["denali"].to<JsonObject>();
  den["day"] = c.denaliDay;
  den["low"] = c.denaliLow;
  den["high"] = c.denaliHigh;
  den["spot"] = c.denaliSpot;

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

  JsonObjectConst col = doc["colors"];
  if (!col.isNull()) {
    c.drlWhiteDay = rgbFrom(col["drlWhiteDay"], c.drlWhiteDay);
    c.drlWhiteNight = rgbFrom(col["drlWhiteNight"], c.drlWhiteNight);
    c.drlDimRedDay = rgbFrom(col["drlDimRedDay"], c.drlDimRedDay);
    c.drlDimRedNight = rgbFrom(col["drlDimRedNight"], c.drlDimRedNight);
    c.indicatorOrange = rgbFrom(col["indicatorOrange"], c.indicatorOrange);
    c.brakeRed = rgbFrom(col["brakeRed"], c.brakeRed);
  }

  JsonObjectConst den = doc["denali"];
  if (!den.isNull()) {
    c.denaliDay = (uint8_t)(den["day"] | c.denaliDay);
    c.denaliLow = (uint8_t)(den["low"] | c.denaliLow);
    c.denaliHigh = (uint8_t)(den["high"] | c.denaliHigh);
    c.denaliSpot = (uint8_t)(den["spot"] | c.denaliSpot);
  }

  return c;
}
