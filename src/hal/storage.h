#pragma once
#include <string>

namespace storage {
  bool begin();
  std::string readConfig();               // "" if missing
  bool writeConfig(const std::string& json);
}
