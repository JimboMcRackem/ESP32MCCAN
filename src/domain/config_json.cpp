#include "domain/config_json.h"
#include <ArduinoJson.h>
#include <cstring>

static const char* kFuncNames[(size_t)Function::COUNT] = {
  "run", "leftInd", "rightInd", "frontBrake", "rearBrake",
  "lowBeam", "highBeam", "highBeamFlash", "dayNight", "kickStand"
};

static uint8_t clampPercent(int v) {
  return (uint8_t)(v < 0 ? 0 : v > 100 ? 100 : v);
}

static int clampInt(int v, int lo, int hi) { return v < lo ? lo : v > hi ? hi : v; }

// A mapped signal is written under maps.<name>; an unmapped one is left out,
// and an absent one reads back unmapped.
static void signalToJson(JsonObject maps, const char* name, const NumSignal& s) {
  if (!s.mapped()) return;
  JsonObject o = maps[name].to<JsonObject>();
  o["id"] = s.id;
  o["start"] = s.startBit;
  o["len"] = s.length;
  o["be"] = s.bigEndian;
  o["signed"] = s.isSigned;
  o["scale"] = s.scale;
  o["offset"] = s.offset;
}

static NumSignal signalFromJson(JsonObjectConst o) {
  NumSignal s;
  if (o.isNull()) return s;
  s.id = o["id"] | 0u;
  s.startBit = (uint8_t)clampInt(o["start"] | 0, 0, 63);
  const int len = o["len"] | 0;
  s.length = (uint8_t)(len >= 1 && len <= 32 ? len : 0);   // out of range = unmapped
  s.bigEndian = o["be"] | false;
  s.isSigned = o["signed"] | false;
  s.scale = o["scale"] | 1.0f;
  s.offset = o["offset"] | 0.0f;
  return s;
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

  signalToJson(maps, "speed", c.speedSignal);
  signalToJson(maps, "lean", c.leanSignal);

  doc["blinkPeriodMs"] = c.blinkPeriodMs;
  doc["nightHoldMs"] = c.nightHoldMs;
  doc["auxOffOnIndicateHighBeam"] = c.auxOffOnIndicateHighBeam;
  doc["auxLowDuty"] = c.auxLowDuty;
  doc["auxFullDuty"] = c.auxFullDuty;
  doc["speedScaleEnable"] = c.speedScaleEnable;
  doc["hbSlowKmh"] = c.hbSlowKmh;
  doc["hbFullKmh"] = c.hbFullKmh;
  doc["hbSlowDuty"] = c.hbSlowDuty;
  doc["leanEnable"] = c.leanEnable;
  doc["leanStartDeg"] = c.leanStartDeg;
  doc["leanFullDeg"] = c.leanFullDeg;
  doc["leanBoostDuty"] = c.leanBoostDuty;
  doc["leanDimDuty"] = c.leanDimDuty;
  doc["leanMinKmh"] = c.leanMinKmh;
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
    // Number signals sit beside the bit maps; the loop above reads only the
    // ten function names, so it never sees these keys.
    c.speedSignal = signalFromJson(maps["speed"]);
    c.leanSignal  = signalFromJson(maps["lean"]);
  }

  c.blinkPeriodMs = doc["blinkPeriodMs"] | c.blinkPeriodMs;
  // nightHoldMs replaced spotHoldMs; a config saved before the rename keeps
  // its hold time.
  c.nightHoldMs = doc["nightHoldMs"] | (doc["spotHoldMs"] | c.nightHoldMs);
  // auxDarkenOnIndicate (protocol 5-6) is gone: the indicating side's pod is
  // now always off at night, so the old key has nothing left to set.
  c.auxOffOnIndicateHighBeam = doc["auxOffOnIndicateHighBeam"] | c.auxOffOnIndicateHighBeam;
  // Read wide and clamp before narrowing, so 250 or -5 cannot wrap a uint8_t.
  c.auxLowDuty  = clampPercent(doc["auxLowDuty"]  | (int)c.auxLowDuty);
  c.auxFullDuty = clampPercent(doc["auxFullDuty"] | (int)c.auxFullDuty);
  c.speedScaleEnable = doc["speedScaleEnable"] | c.speedScaleEnable;
  c.hbSlowKmh  = (uint16_t)clampInt(doc["hbSlowKmh"] | (int)c.hbSlowKmh, 0, 300);
  c.hbFullKmh  = (uint16_t)clampInt(doc["hbFullKmh"] | (int)c.hbFullKmh, 0, 300);
  c.hbSlowDuty = clampPercent(doc["hbSlowDuty"] | (int)c.hbSlowDuty);
  c.leanEnable = doc["leanEnable"] | c.leanEnable;
  c.leanStartDeg  = (uint8_t)clampInt(doc["leanStartDeg"] | (int)c.leanStartDeg, 0, 60);
  c.leanFullDeg   = (uint8_t)clampInt(doc["leanFullDeg"] | (int)c.leanFullDeg, 1, 70);
  c.leanBoostDuty = clampPercent(doc["leanBoostDuty"] | (int)c.leanBoostDuty);
  c.leanDimDuty   = clampPercent(doc["leanDimDuty"] | (int)c.leanDimDuty);
  c.leanMinKmh    = (uint16_t)clampInt(doc["leanMinKmh"] | (int)c.leanMinKmh, 0, 300);
  // Unknown or non-string values resolve to the default, Generate, rather
  // than to an undefined enum value.
  const char* fs = doc["flashSource"].as<const char*>();
  c.flashSource = FlashSource::Generate;
  if (fs) {
    if (!strcmp(fs, "follow"))    c.flashSource = FlashSource::Follow;
    else if (!strcmp(fs, "auto")) c.flashSource = FlashSource::Auto;
  }
  c.testMaxMs = doc["testMaxMs"] | c.testMaxMs;

  return c;
}
