#include "hal/storage.h"
#include <Arduino.h>
#include <LittleFS.h>

static const char* kPath = "/config.json";

namespace storage {

bool begin() { return LittleFS.begin(true); }   // format on first run

std::string readConfig() {
  File f = LittleFS.open(kPath, "r");
  if (!f) return "";
  std::string out;
  out.reserve(f.size());
  while (f.available()) out.push_back((char)f.read());
  f.close();
  return out;
}

bool writeConfig(const std::string& json) {
  File f = LittleFS.open(kPath, "w");
  if (!f) return false;
  f.print(json.c_str());
  f.close();
  return true;
}

}  // namespace storage
