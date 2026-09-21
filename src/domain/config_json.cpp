#include "domain/config_json.h"
#include <ArduinoJson.h>

static const char* kFuncNames[(size_t)Function::COUNT] = {
  "run", "leftInd", "rightInd", "frontBrake", "rearBrake",
  "lowBeam", "highBeam", "highBeamFlash", "dayNight", "kickStand"
};

static void colorTo(JsonObject o, const ColorLevel& c) {
  JsonArray h = o["hue"].to<JsonArray>();
  h.add(c.hue.r); h.add(c.hue.g); h.add(c.hue.b);
  o["level"] = c.level;
}

// Accepts both shapes:
//   {"hue":[r,g,b],"level":n}   current
//   [r,g,b]                     written before the hue/level split
// The bare triple is migrated duty-preserving, so upgrading does not change
// how the bike looks. Serialization always writes the new shape, so the
// first save completes the upgrade.
static ColorLevel colorFrom(JsonVariantConst v, ColorLevel def) {
  if (v.is<JsonArrayConst>()) {
    JsonArrayConst a = v.as<JsonArrayConst>();
    if (a.size() != 3) return def;
    return colorFromRgb(Rgb{ (uint8_t)a[0].as<int>(),
                             (uint8_t)a[1].as<int>(),
                             (uint8_t)a[2].as<int>() });
  }
  if (v.is<JsonObjectConst>()) {
    JsonObjectConst o = v.as<JsonObjectConst>();
    JsonArrayConst a = o["hue"];
    if (a.size() != 3) return def;
    ColorLevel c;
    c.hue = Rgb{ (uint8_t)a[0].as<int>(),
                 (uint8_t)a[1].as<int>(),
                 (uint8_t)a[2].as<int>() };
    c.level = (uint8_t)(o["level"] | 255);
    return c;
  }
  return def;
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
  doc["testMaxMs"] = c.testMaxMs;

  JsonObject col = doc["colors"].to<JsonObject>();
  colorTo(col["drlWhiteDay"].to<JsonObject>(),     c.drlWhiteDay);
  colorTo(col["drlWhiteNight"].to<JsonObject>(),   c.drlWhiteNight);
  colorTo(col["drlDimRedDay"].to<JsonObject>(),    c.drlDimRedDay);
  colorTo(col["drlDimRedNight"].to<JsonObject>(),  c.drlDimRedNight);
  colorTo(col["indicatorOrange"].to<JsonObject>(), c.indicatorOrange);
  colorTo(col["brakeRed"].to<JsonObject>(),        c.brakeRed);

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
  c.testMaxMs = doc["testMaxMs"] | c.testMaxMs;

  JsonObjectConst col = doc["colors"];
  if (!col.isNull()) {
    c.drlWhiteDay     = colorFrom(col["drlWhiteDay"], c.drlWhiteDay);
    c.drlWhiteNight   = colorFrom(col["drlWhiteNight"], c.drlWhiteNight);
    c.drlDimRedDay    = colorFrom(col["drlDimRedDay"], c.drlDimRedDay);
    c.drlDimRedNight  = colorFrom(col["drlDimRedNight"], c.drlDimRedNight);
    c.indicatorOrange = colorFrom(col["indicatorOrange"], c.indicatorOrange);
    c.brakeRed        = colorFrom(col["brakeRed"], c.brakeRed);
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
