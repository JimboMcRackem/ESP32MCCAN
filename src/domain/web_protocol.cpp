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
      // A missing or non-numeric zones field must be rejected, not treated
      // as mask 0: that would silently turn a malformed request into
      // "energise nothing" while still reporting success, which contradicts
      // the reasoning below for the out-of-range case.
      if (!doc["zones"].is<uint32_t>()) {
        act.error = "zones field missing or not a non-negative integer";
        return act;
      }
      const uint32_t mask = doc["zones"];
      // Reject rather than truncate: a client sending a bit we do not have is
      // out of sync with the firmware, and silently dropping it would make the
      // test tab lie about what it just energised.
      if (mask >= (1u << (uint32_t)OUT_COUNT)) {
        act.error = "zones mask has bits above OUT_COUNT";
        return act;
      }
      tm.zones.on = (uint16_t)mask;
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
  doc["zones"] = t.zones.on;
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
