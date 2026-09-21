#include "domain/web_protocol.h"
#include "domain/config_json.h"
#include <ArduinoJson.h>

ProtocolAction handleRequest(const std::string& json) {
  ProtocolAction act;
  JsonDocument doc;
  if (deserializeJson(doc, json) != DeserializationError::Ok) {
    act.error = "malformed json";
    return act;
  }

  const char* type = doc["type"] | "";
  std::string t = type;

  if (t == "get_config") {
    act.sendConfig = true;
    return act;
  }

  if (t == "set_config") {
    JsonObjectConst cfg = doc["config"];
    if (cfg.isNull()) {
      act.error = "set_config missing config";
      return act;
    }
    std::string inner;
    serializeJson(cfg, inner);
    bool ok = false;
    Config c = configFromJson(inner, ok);
    if (!ok) {
      act.error = "invalid config";
      return act;
    }
    act.applyConfig = true;
    act.cfgOut = c;
    return act;
  }

  if (t == "discovery") {
    act.setDiscovery = true;
    act.discoveryOut = doc["enable"] | false;
    return act;
  }

  if (t == "test") {
    const char* modeStr = doc["mode"] | "";
    std::string m = modeStr;
    TestMode tm;

    if (m == "off") {
      tm.kind = TestKind::Off;
    } else if (m == "scenario") {
      const char* name = doc["scenario"] | "";
      if (!scenarioByName(name, tm.scenario)) {
        act.error = std::string("unknown scenario: ") + name;
        return act;
      }
      tm.kind = TestKind::Scenario;
    } else if (m == "zones") {
      JsonArrayConst zs = doc["zones"];
      if (zs.size() != 4) {
        act.error = "test zones must be 4 rgb triples";
        return act;
      }
      // ChannelIndex corner order: front L, front R, rear L, rear R.
      Rgb* dst[4] = { &tm.zones.frontL, &tm.zones.frontR,
                      &tm.zones.rearL,  &tm.zones.rearR };
      int zi = 0;
      for (JsonArrayConst z : zs) {
        if (z.size() != 3) {
          act.error = "test zone must be an rgb triple";
          return act;
        }
        int v[3];
        for (int k = 0; k < 3; ++k) {
          v[k] = z[k] | -1;
          if (v[k] < 0 || v[k] > 255) {
            act.error = "test zone value out of range";
            return act;
          }
        }
        *dst[zi++] = Rgb{ (uint8_t)v[0], (uint8_t)v[1], (uint8_t)v[2] };
      }
      const int den = doc["denali"] | 0;
      if (den < 0 || den > 255) {
        act.error = "test denali out of range";
        return act;
      }
      tm.zones.denali = (uint8_t)den;
      tm.kind = TestKind::Zones;
    } else {
      act.error = "test mode must be off, scenario or zones";
      return act;
    }

    act.setTest = true;
    act.testOut = tm;
    return act;
  }

  act.error = "unknown type";
  return act;
}

std::string configMessage(const Config& c) {
  JsonDocument doc;
  doc["type"] = "config";
  doc["protocolVersion"] = kProtocolVersion;
  doc["config"] = serialized(configToJson(c));  // insert pre-formatted JSON verbatim
  std::string out;
  serializeJson(doc, out);
  return out;
}

std::string framesMessage(const CanFrameSnapshot* frames, int count) {
  JsonDocument doc;
  doc["type"] = "frames";
  JsonArray arr = doc["frames"].to<JsonArray>();
  for (int i = 0; i < count; ++i) {
    JsonObject f = arr.add<JsonObject>();
    f["id"] = frames[i].id;
    JsonArray d = f["data"].to<JsonArray>();
    for (int b = 0; b < 8; ++b) d.add(frames[i].data[b]);
  }
  std::string out;
  serializeJson(doc, out);
  return out;
}

std::string errorMessage(const std::string& msg) {
  JsonDocument doc;
  doc["type"] = "error";
  doc["message"] = msg;
  std::string out;
  serializeJson(doc, out);
  return out;
}

std::string testStateMessage(const TestMode& t, const Config& cfg, uint32_t nowMs) {
  JsonDocument doc;
  doc["type"] = "test_state";
  doc["active"] = (t.kind != TestKind::Off);
  doc["kind"] = t.kind == TestKind::Scenario ? "scenario"
              : t.kind == TestKind::Zones    ? "zones"
                                             : "off";
  uint32_t remaining = 0;
  if (t.kind != TestKind::Off) {
    const uint32_t elapsed = nowMs - t.startedMs;     // rollover-safe
    remaining = elapsed >= cfg.testMaxMs ? 0u : (cfg.testMaxMs - elapsed);
  }
  doc["remainingMs"] = remaining;
  std::string out;
  serializeJson(doc, out);
  return out;
}
