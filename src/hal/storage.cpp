#include "hal/storage.h"
#include <Arduino.h>
#include <LittleFS.h>
#include <Preferences.h>
#include "domain/wifi_settings.h"

static const char* kLegacyPath = "/config.json";
static Preferences g_prefs;   // namespace stays open for the program's lifetime
static bool g_open = false;

namespace storage {

std::string readConfig() {
  if (!g_open) return "";
  size_t n = g_prefs.getBytesLength("config");
  if (n == 0) return "";
  std::string out(n, '\0');
  size_t got = g_prefs.getBytes("config", &out[0], n);
  out.resize(got);
  return out;
}

bool writeConfig(const std::string& json) {
  if (!g_open) return false;
  return g_prefs.putBytes("config", json.data(), json.size()) == json.size();
}

std::string readWifiPassword() {
  if (!g_open || !g_prefs.isKey("wifi_pass")) return kDefaultWifiPassword;
  String s = g_prefs.getString("wifi_pass", kDefaultWifiPassword);
  return std::string(s.c_str());
}

bool writeWifiPassword(const std::string& p) {
  if (!g_open) return false;
  return g_prefs.putString("wifi_pass", p.c_str()) == p.size();
}

bool isDefaultWifiPassword() {
  if (!g_open || !g_prefs.isKey("wifi_pass")) return true;
  return readWifiPassword() == kDefaultWifiPassword;
}

void requestResetOnNextBoot() {
  if (g_open) g_prefs.putUChar("reset_pend", 1);
}

void eraseAll() {
  if (g_open) g_prefs.clear();
}

bool begin() {
  g_open = g_prefs.begin("mccan", false);
  if (!g_open) {
    Serial.println("storage: NVS open failed");
    return false;
  }

  if (g_prefs.getUChar("reset_pend", 0) == 1) {
    eraseAll();
    Serial.println("storage: pending factory reset performed");
  }

  // Legacy LittleFS config: mount without formatting, migrate once, delete.
  if (LittleFS.begin(false)) {
    bool legacyHas = LittleFS.exists(kLegacyPath);
    if (legacyHas) {
      bool nvsHas = g_prefs.getBytesLength("config") > 0;
      // Delete the legacy file only once NVS holds a config: either it already
      // did (NVS wins), or the import below succeeded. A failed read or write
      // keeps the file, so the next boot tries again.
      bool done = true;
      if (pickConfigSource(nvsHas, legacyHas) == ConfigSource::Legacy) {
        done = false;
        File f = LittleFS.open(kLegacyPath, "r");
        if (f) {
          std::string data;
          data.reserve(f.size());
          while (f.available()) data.push_back((char)f.read());
          f.close();
          done = writeConfig(data);
        }
        Serial.println(done ? "storage: legacy config migrated to NVS"
                            : "storage: legacy config import failed; /config.json kept");
      }
      if (done) LittleFS.remove(kLegacyPath);
    }
    LittleFS.end();
  } else {
    Serial.println("storage: LittleFS mount failed, legacy migration skipped");
  }
  return true;
}

}  // namespace storage
