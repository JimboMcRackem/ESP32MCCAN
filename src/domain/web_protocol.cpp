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

  act.error = "unknown type";
  return act;
}

std::string configMessage(const Config& c) {
  JsonDocument doc;
  doc["type"] = "config";
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
