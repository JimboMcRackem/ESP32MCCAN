#pragma once
#include <string>

namespace storage {
  bool begin();                                  // opens NVS, honours pending reset, migrates legacy config
  std::string readConfig();                      // "" if none
  bool writeConfig(const std::string& json);
  std::string readWifiPassword();                // kDefaultWifiPassword if none stored
  bool writeWifiPassword(const std::string& p);
  bool isDefaultWifiPassword();
  void requestResetOnNextBoot();                 // sets reset_pend = 1
  void eraseAll();                               // erases the whole "mccan" namespace
}
